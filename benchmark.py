#!/usr/bin/env python3
"""
Usage:
  python benchmark.py                   # runs cases/ directory
  python benchmark.py cases/ --out results/run1.json
  python benchmark.py cases/tc_001.json # single case
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from runner.evaluators import score_response, score_stt, score_tool_calls
from runner.pipeline import run_case

load_dotenv()

PASS_THRESHOLDS = {
    "wer": 0.30,           # generous given Singlish; report but don't punish heavily
    "tool_score": 0.80,
    "intent_resolved": 1,
    "no_forbidden": True,  # any forbidden tool call = fail regardless
}


async def run_benchmark(cases_dir: str, out: str = "results/report.json"):
    cases_path = Path(cases_dir)
    case_files = sorted(cases_path.glob("*.json")) if cases_path.is_dir() else [cases_path]

    results = []
    print(f"\nRunning {len(case_files)} cases...\n")
    print(f"{'ID':<8} {'Category':<20} {'WER':>6} {'Tools':>10} {'Intent':>8} {'Pass':>6}")
    print("-" * 64)

    for case_file in case_files:
        case = json.loads(case_file.read_text())
        audio = case_file.parent / case["audio"]

        try:
            trace = await run_case(str(audio))
        except Exception as e:
            print(f"{case['id']:<8} ERROR: {e}")
            continue

        # evaluted based on three dimension
        stt   = score_stt(trace, case)
        tools = score_tool_calls(trace, case)
        resp  = score_response(trace, case)

        passed = (
            stt["wer"]                      <= PASS_THRESHOLDS["wer"]
            and tools["score"]              >= PASS_THRESHOLDS["tool_score"]
            and resp.get("intent_resolved") >= PASS_THRESHOLDS["intent_resolved"]
            and not tools["forbidden_hits"]
        )

        results.append({
            "id": case["id"],
            "category": case["category"],
            "description": case.get("description", ""),
            "stt": stt,
            "tools": tools,
            "response": resp,
            "passed": passed,
            "trace": {
                "transcript": trace["transcript"],
                "tool_calls": trace["tool_calls"],
                "response_text": trace["response_text"],
            },
        })

        status = "✓" if passed else "✗"
        print(
            f"{case['id']:<8} {case['category']:<20} "
            f"{stt['wer']:>6.2f} {tools['verdict']:>10} "
            f"{resp.get('intent_resolved','?'):>8} {status:>6}"
        )

    # Aggregate by category
    categories = sorted(set(r["category"] for r in results))
    by_category = {}
    for cat in categories:
        cat_r = [r for r in results if r["category"] == cat]
        by_category[cat] = {
            "n": len(cat_r),
            "pass_rate": round(sum(r["passed"] for r in cat_r) / len(cat_r), 2),
            "avg_wer": round(sum(r["stt"]["wer"] for r in cat_r) / len(cat_r), 3),
            "tool_accuracy": round(sum(r["tools"]["score"] for r in cat_r) / len(cat_r), 2),
            "intent_resolved": round(sum(r["response"].get("intent_resolved", 0) for r in cat_r) / len(cat_r), 2),
            "forbidden_hit_rate": round(sum(1 for r in cat_r if r["tools"]["forbidden_hits"]) / len(cat_r), 2),
        }

    report = {
        "total": len(results),
        "passed": sum(r["passed"] for r in results),
        "pass_rate": round(sum(r["passed"] for r in results) / max(len(results), 1), 2),
        "by_category": by_category,
        "cases": results,
    }

    print(f"\n{'─'*64}")
    print(f"\n{'Category':<22} {'N':>4} {'Pass%':>7} {'WER':>7} {'Tools':>7} {'Intent':>8} {'Forbid':>8}")
    print("-" * 66)
    for cat, s in by_category.items():
        print(f"{cat:<22} {s['n']:>4} {s['pass_rate']*100:>6.0f}% "
              f"{s['avg_wer']:>7.3f} {s['tool_accuracy']:>7.2f} "
              f"{s['intent_resolved']:>8.2f} {s['forbidden_hit_rate']:>8.2f}")

    Path(out).parent.mkdir(exist_ok=True, parents=True)
    Path(out).write_text(json.dumps(report, indent=2))
    print(f"\nFull report saved → {out}\n")
    return report


if __name__ == "__main__":
    cases = sys.argv[1] if len(sys.argv) > 1 else "cases/"
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    out   = sys.argv[2] if len(sys.argv) > 2 else f"results/{timestamp}_report.json"
    asyncio.run(run_benchmark(cases, out))
