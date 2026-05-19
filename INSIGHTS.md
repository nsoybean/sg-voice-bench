# Insights

A running log of things I learned building this. Small observations, surprises, dead ends.

---

<!-- Add new entries at the top, newest first -->

## Tool call evaluation has four moving parts

To properly evaluate tool calls: check for expected calls (did the agent call the right tools?), track hallucinations (tools called that were never expected), measure accuracy as a ratio of correct calls over total expected, and blacklist certain tools that should never be called for a given intent — any blacklist hit is an automatic fail regardless of everything else.
