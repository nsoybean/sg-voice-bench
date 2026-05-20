import json

import jiwer
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()


# --- 1. STT accuracy ---

def score_stt(trace: dict, case: dict) -> dict:
    reference = case["reference_transcript"].lower().strip()
    hypothesis = (trace["transcript"] or "").lower().strip()

    if not hypothesis:
        return {"wer": 1.0, "particle_retention": 0.0, "transcript_got": "", "note": "empty transcript"}

    wer = jiwer.wer(reference, hypothesis)

    particles = ["lah", "leh", "sia", "mah", "lor", "eh", "wah", "ah", "anot", "boleh", "sudah"]
    expected_particles = [p for p in particles if p in reference]
    retained = [p for p in expected_particles if p in hypothesis]

    return {
        "wer": round(wer, 3),
        "particle_retention": round(len(retained) / max(len(expected_particles), 1), 2),
        "transcript_got": hypothesis,
        "transcript_expected": reference,
        "particles_expected": expected_particles,
        "particles_retained": retained,
    }


# --- 2. VAD cut detection ---

def check_vad_cut(trace: dict, case: dict, stt: dict) -> dict:
    """
    Detects if VAD likely cut the turn before the user finished speaking.
    Uses word coverage: if the transcript is much shorter than the reference,
    the pipeline probably committed to a turn mid-utterance.

    Only meaningful for cases where the full utterance matters — particularly
    intent_switch category where the correction comes in the second half.
    The stt argument is accepted for future reuse (e.g. referencing the
    already-normalised transcript) without re-processing.
    """
    reference_words = len(case["reference_transcript"].split())
    transcript_words = len((trace["transcript"] or "").split())
    coverage = transcript_words / max(reference_words, 1)

    # 0.6 allows for Singlish particle drops without false-positiving on them.
    # Caller is responsible for only acting on this flag in relevant categories.
    likely_cut = coverage < 0.6

    return {
        "coverage": round(coverage, 2),
        "likely_vad_cut": likely_cut,
        "reference_words": reference_words,
        "transcript_words": transcript_words,
    }


# --- 3. Tool call accuracy ---

def score_tool_calls(trace: dict, case: dict) -> dict:
    """
    Checks three things:
    1. Required tools called with correct arg VALUES (not just keys).
    2. No forbidden tools called.
    3. Reports hallucinated tools (called but not expected and not forbidden).

    Note: 'expected_tools' may include either-or alternatives (handled by treating
    each entry as required unless the case schema specifies otherwise). For v1 we
    treat the list as a permissive superset — any of the expected tools satisfies
    that entry, and forbidden_tools is the strict check.
    """
    expected = case.get("expected_tools", [])
    forbidden = case.get("forbidden_tools", [])
    actual = trace["tool_calls"]
    actual_names = [t["name"] for t in actual]

    # --- forbidden check ---
    forbidden_hits = []
    for f in forbidden:
        if isinstance(f, str):
            if f in actual_names:
                forbidden_hits.append({"tool": f, "called_with": [t["args"] for t in actual if t["name"] == f]})
        elif isinstance(f, dict):
            # forbidden = {"name": "cancel_order", "args": {"order_id": "ORD-8830"}}
            for t in actual:
                if t["name"] == f["name"]:
                    args_match = all(str(t["args"].get(k)) == str(v) for k, v in f.get("args", {}).items())
                    if args_match or not f.get("args"):
                        forbidden_hits.append({"tool": f["name"], "args": t["args"]})

    # --- expected check ---
    per_tool = []
    for exp in expected:
        found = next((t for t in actual if t["name"] == exp["name"]), None)
        if not found:
            per_tool.append({"tool": exp["name"], "verdict": "missing_call"})
            continue

        req_args = exp.get("required_args", {})
        if req_args:
            mismatches = {k: {"expected": v, "got": found["args"].get(k)}
                          for k, v in req_args.items()
                          if str(found["args"].get(k, "")).strip() != str(v).strip()}
            if mismatches:
                per_tool.append({"tool": exp["name"], "verdict": "wrong_args", "mismatches": mismatches})
            else:
                per_tool.append({"tool": exp["name"], "verdict": "correct"})
        else:
            per_tool.append({"tool": exp["name"], "verdict": "correct"})

    expected_names = {e["name"] for e in expected}
    hallucinated = [n for n in actual_names if n not in expected_names]

    correct_count = sum(1 for t in per_tool if t["verdict"] == "correct")
    score = round(correct_count / max(len(expected), 1), 2) if expected else (1.0 if not actual else 0.5)

    # Forbidden hits are an automatic fail
    if forbidden_hits:
        verdict = "forbidden_called"
    elif correct_count == len(expected) and not [h for h in hallucinated if h not in [e["name"] for e in expected]]:
        verdict = "correct"
    else:
        verdict = "incorrect"

    return {
        "score": 0.0 if forbidden_hits else score,
        "per_tool": per_tool,
        "forbidden_hits": forbidden_hits,
        "hallucinated_tools": hallucinated,
        "redundant_calls": len(actual) - len(set(actual_names)),
        "verdict": verdict,
    }


# --- 4. Response quality (LLM-as-judge) ---

def score_response(trace: dict, case: dict) -> dict:
    response = (trace["response_text"] or "").strip()
    themes = case.get("expected_response_themes", [])
    intent = case.get("expected_intent", "unknown")

    if not response:
        return {"intent_resolved": 0, "themes_covered": 0.0, "hallucination": 1,
                "word_count": 0, "note": "empty response"}

    word_count = len(response.split())

    prompt = f"""Evaluate this voice agent response. Reply with JSON only — no explanation.

User intent: {intent}
Expected response themes (any of these is good): {themes}
Agent response: "{response}"

Note: If the intent is ambiguous, asking a clarifying question IS a valid resolution (set intent_resolved=1).
If the intent is out-of-scope, politely declining IS a valid resolution (set intent_resolved=1).

Score:
- intent_resolved: 1 if the response appropriately addresses the user's need (including by clarifying or declining), else 0
- themes_covered: float 0-1, fraction of expected themes present (or related concept)
- hallucination: 1 if the agent invented false information (fake order IDs, fake amounts, etc.), else 0

JSON only:"""

    r = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )

    try:
        result = json.loads(r.choices[0].message.content)
        result["word_count"] = word_count
        # Deterministic conciseness: <25 words = good for voice, 25-50 = ok, >50 = too long
        result["conciseness"] = 3 if word_count < 25 else (2 if word_count <= 50 else 1)
        return result
    except Exception:
        return {"intent_resolved": 0, "themes_covered": 0.0, "hallucination": 0,
                "word_count": word_count, "conciseness": 2, "note": "judge parse error"}
