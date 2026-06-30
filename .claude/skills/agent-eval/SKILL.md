---
name: agent-eval
description: Use when evaluating the OUTPUT QUALITY of an LLM, RAG pipeline, or agent — faithfulness, answer relevancy, context precision/recall, or agent trajectory. Triggers "evaluate my RAG", "RAGAS", "is my agent any good", "hallucination check", "agent trajectory", "LLM-as-judge". NOT for classical ML/DL metrics like accuracy/F1/RMSE (use model-eval).
---

# Skill: Agent & RAG Evaluation

You cannot improve what you do not measure, and LLM output can't be scored with
accuracy/F1 — it needs semantic, often LLM-as-judge, metrics. Use **RAGAS** for RAG;
add **trajectory** checks for agents.

## Split the problem: retrieval vs. generation
- **Retrieval** — did we fetch the right chunks? → `context_precision`, `context_recall`.
- **Generation** — given those chunks, is the answer grounded and on-point? →
  `faithfulness` (is every claim supported by context? = hallucination check),
  `answer_relevancy` (does it address the actual question?).

Read the pair together: high faithfulness + low relevancy = grounded but rambling
(a prompt problem). Good faithfulness needs good retrieval first.

## RAGAS skeleton (class-based metrics, current API)
```python
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import Faithfulness, ResponseRelevancy, LLMContextPrecisionWithoutReference

data = Dataset.from_dict({
    "question": [...],
    "answer": [...],          # your pipeline's output
    "contexts": [[...], ...], # retrieved chunks per question
    # "ground_truth": [...],  # add when you have reference answers
})

result = evaluate(data, metrics=[
    Faithfulness(),
    ResponseRelevancy(),
    LLMContextPrecisionWithoutReference(),
])
print(result)                 # {'faithfulness': 0.89, 'answer_relevancy': 0.87, ...}
df = result.to_pandas()       # per-row scores to find the failures
```
Install: `uv add ragas datasets`. RAGAS is **reference-free** for these — you don't need
gold answers to start.

## For agents, also check the trajectory
A right answer reached the wrong way is still a bug. Evaluate:
- **Tool choice** — did it call the correct tools, in a sane order?
- **Step count** — did it loop or take a needlessly long path?
- **Termination** — did it stop at the right point?

## Honest caveats
- LLM-as-judge is itself a model — it has variance. Run the eval set more than once and
  watch the spread, don't trust a single run.
- A high faithfulness score with stale/wrong context still yields wrong answers; the
  metric checks grounding, not truth. Keep a small human-checked golden set.

Always wire the eval into CI against a fixed golden set so quality regressions surface
before users hit them.
