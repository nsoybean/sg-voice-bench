# Insights

A running log of things I learned building this. Small observations, surprises, dead ends.

---

<!-- Add new entries at the top, newest first -->

## Premature VAD cutoff is a silent upstream failure

If VAD ends the turn too early, the STT only transcribes the first half of what the user said — so a mid-sentence intent change like "cancel my order — wait, help me do X instead" gets truncated before it reaches the LLM. The model isn't wrong, it just never saw the correction. Hard to catch because the LLM response can look totally reasonable against the partial transcript. The bug is in the pipeline upstream of the LLM, at the VAD/STT boundary.

## Turn detection and interruption

VAD (voice activity detection) is the most common way to detect end-of-turn — just watch for silence. Beyond that there's STT endpointing, context-aware turn detector models, and server-side detection built into realtime LLMs. False interruptions (VAD fires but no words were spoken) are a real problem — agents can be configured to resume speaking after a short timeout if the transcript comes back empty. Good reference: https://docs.livekit.io/agents/logic/turns/

## Tool call evaluation has four moving parts

To properly evaluate tool calls: check for expected calls (did the agent call the right tools?), track hallucinations (tools called that were never expected), measure accuracy as a ratio of correct calls over total expected, and blacklist certain tools that should never be called for a given intent — any blacklist hit is an automatic fail regardless of everything else.
