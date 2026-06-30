# Rule: RAG

- Keep **ingestion** and **retrieval** as separate, independently testable paths.
- Be explicit about chunking: size, overlap, and *why* for this data. Don't default to
  1000/200 silently — justify it.
- **Evaluate before tuning.** Before optimizing retrieval, propose a small eval
  (a handful of question→expected-chunk pairs) so we measure, not guess.
- Always carry source metadata through the pipeline so answers can cite their chunks.
- For embeddings, state the model and dimensions (local Ollama vs. hosted) and the
  cost/latency trade-off.
- Separate "retrieval quality" problems from "generation" problems when debugging —
  say which layer you think is at fault and how to confirm.
