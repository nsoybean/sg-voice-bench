# sg-voice-bench

> Evaluating voice agents on Singapore speech: Singlish, code-switching, hawker-centre noise, mixed Mandarin/Malay.

A small CLI benchmark that runs pre-recorded audio through a voice agent pipeline (STT → LLM with tools → TTS) and scores transcription accuracy, tool call correctness, and response quality.

**This is a learning-in-public project.** I'm new to voice AI. The point isn't to ship a definitive benchmark — it's to surface what actually breaks when you point a standard voice stack at Singapore speech, and to learn the evaluation craft by doing it.

Feedback, corrections, and "you got this wrong because…" very welcome.

---

## What's in here

- **30 test cases** across 7 categories (code-switching, Singlish grammar, background noise, multilingual, intent switching, ambiguous reference, out-of-scope)
- **A runner** built on OpenAI's `VoicePipeline` + Agents SDK, with a representative food-delivery agent
- **Three scorers**: WER + Singlish particle retention, tool-call correctness (including forbidden-tool detection for intent switching), LLM-as-judge response quality
- **Seeded state** so tool calls have real arg values to verify against, not just function names

Single-turn evaluation only — one audio file in, one agent response out. See [PLAN.md](./PLAN.md) for the full design rationale and [FINDINGS.md](./FINDINGS.md) for what I actually learned running it.

---

## Quick start

```bash
git clone https://github.com/nsoybean/sg-voice-bench.git
cd sg-voice-bench
pip install -r requirements.txt
cp .env.example .env  # add your OPENAI_API_KEY

python benchmark.py cases/                 # run all 30 cases
python benchmark.py cases/tc_001.json      # single case
python benchmark.py cases/ results/run.json
```

Each run saves a timestamped JSON report to `results/` (e.g. `results/20250115T143000_report.json`). That folder is gitignored — results stay local and don't get committed.

---

## Results

_Populated after the first real run. Numbers below are placeholders until then._

| Category            | N   | Pass rate | Avg WER | Tool accuracy | Intent resolved | Forbidden-tool hits |
| ------------------- | --- | --------- | ------- | ------------- | --------------- | ------------------- |
| Code-switching      | 6   | TBD       | TBD     | TBD           | TBD             | TBD                 |
| Singlish grammar    | 6   | TBD       | TBD     | TBD           | TBD             | TBD                 |
| Background noise    | 6   | TBD       | TBD     | TBD           | TBD             | TBD                 |
| Multilingual        | 4   | TBD       | TBD     | TBD           | TBD             | TBD                 |
| Intent switching    | 4   | TBD       | TBD     | TBD           | TBD             | TBD                 |
| Ambiguous reference | 2   | TBD       | TBD     | TBD           | TBD             | TBD                 |
| Out-of-scope        | 2   | TBD       | TBD     | TBD           | TBD             | TBD                 |

See [FINDINGS.md](./FINDINGS.md) for the interpretation and what surprised me.

---

## How it works

```
audio.m4a → VoicePipeline → ┌─ transcript ─────┐
                            ├─ tool calls ─────┤ → 3 scorers → JSON report
                            └─ response text ──┘
```

Each test case is a `.m4a` + `.json` pair. The JSON specifies the reference transcript, the expected tool trajectory (with concrete arg values from the seeded state), forbidden tools the agent must NOT call, and themes the response should cover. The runner resets state before each case so they don't leak.

The agent is a food-delivery customer support bot with six tools (`list_orders`, `get_order`, `cancel_order`, `list_refunds`, `check_refund_status`, `escalate_to_human`) backed by a small in-memory data store of four orders and one in-flight refund.

---

## Known limitations

I'd rather flag these up front than have someone catch them in the issues:

- **Single-turn only.** No multi-turn flows, no clarification follow-ups, no live barge-in. Many real production failures are multi-turn — this benchmark doesn't touch them.
- **One agent vertical.** Food delivery. Banking or healthcare would have different failure patterns.
- **Synthetic test cases.** I recorded these myself. Real production traffic has more variation in accent, mic, speed, emotion.
- **LLM-as-judge is noisy.** The response scorer is an LLM grading an LLM. I hand-labeled 10 cases to calibrate, but it's still a soft signal.
- **No latency measurement.** End-to-end response time matters a lot for voice UX. Not measured here.
- **WER is unfair to Singlish.** Particles get marked as substitution errors even when communication succeeds. Particle retention rate is reported alongside.

---

## Contributing / feedback

This is a personal experiment, but if you spot something wrong, have suggestions for additional test cases, or know a better way to evaluate any of this — open an issue or DM me. Especially interested in:

- Better metrics for Singlish-aware STT eval
- Test cases I should add (especially ones that test failures I haven't thought of)
- How production teams actually evaluate voice agents

---

## License

MIT. Test audio recorded by me, CC0. Background noise from [freesound.org](https://freesound.org), CC0.
