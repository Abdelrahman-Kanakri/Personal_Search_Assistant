---
name: agent-memory
description: Use when giving an agent memory across turns or sessions — managing conversation history, summarization/trimming, or long-term persistent memory (mem0, vector store, LangGraph Store). Triggers "give my agent memory", "remember across sessions", "mem0", "conversation history is too long", "long-term memory", "persist user preferences". This is about building memory INTO agents (not the .claude/agent-memory config folder).
---

# Skill: Agent Memory

"Memory" is three different problems. Name which one you're solving before coding —
they have different solutions.

1. **Short-term (in-context)** — the running conversation. Bounded by the context
   window, so it needs management, not just appending.
2. **Long-term (persistent)** — facts/preferences that survive across sessions.
   Stored outside the model, retrieved on demand.
3. **Working state** — the agent's scratchpad for the current task (in LangGraph, this
   is your graph state + checkpointer; not the same as long-term memory).

## Short-term: don't just grow the history
The history will overflow the window. Manage it:
- **Trim** — keep the last N turns (cheap, lossy on old context).
- **Summarize** — when history exceeds a threshold, replace old turns with an
  LLM-written summary node, keep recent turns verbatim. Best default for long chats.
- In LangGraph: a checkpointer persists state per thread; add a summarization node that
  fires past a token budget.

## Long-term: store facts, not transcripts
Persisting the whole conversation is wasteful and noisy. Extract durable facts and store
*those*, retrieved by relevance. **mem0** does this extraction + retrieval for you:
```python
from mem0 import Memory          # OSS, self-hosted; configurable with Ollama/local LLM

m = Memory()
m.add(                            # extracts discrete facts, dedupes against existing
    [{"role": "user", "content": "I prefer Python over JS and I'm vegetarian."}],
    user_id="abood",
)
hits = m.search("dietary preferences", user_id="abood")   # semantic retrieval
# inject hits into the next prompt instead of the whole history
```
Install: `uv add mem0ai`. mem0 resolves each fact as ADD/UPDATE/DELETE/NONE, so the
store stays compact instead of accumulating contradictions. Alternatives: a plain
vector store (Supabase/pgvector) if you want full control, or **LangGraph Store** if
you're already in LangGraph and want one less moving part.

## Choosing
- Already on LangGraph, simple needs → checkpointer + LangGraph Store.
- Want fact extraction/dedup handled for you → mem0.
- Need temporal "true from/until" tracking → a graph-memory tool, not plain vectors.

Scope every memory by `user_id` (and `session_id` where relevant), or you'll leak one
user's memories into another's context — the most common and most dangerous bug here.
