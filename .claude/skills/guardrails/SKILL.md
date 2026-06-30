---
name: guardrails
description: Use when validating or constraining LLM input/output — enforcing structured/typed output, blocking unsafe or off-topic responses, preventing prompt injection, or adding retry-on-invalid. Triggers "validate the LLM output", "guardrails", "structured output", "prevent prompt injection", "constrain the model", "the model returns junk sometimes". NOT for tabular data cleaning (use data-prep).
---

# Skill: Guardrails

LLM output is a suggestion, not a contract. Anything downstream that depends on its
shape or safety needs validation at the boundary. Two layers: **structure** (is it the
right shape?) and **policy** (is it safe/on-topic?).

## Layer 1 — structure first (cheapest, catches the most)
Make the model return typed data and validate with Pydantic. If it fails, you get a
precise error to retry on — not a silent bad value.
```python
from pydantic import BaseModel, field_validator

class Extraction(BaseModel):
    sentiment: str
    score: float

    @field_validator("sentiment")
    @classmethod
    def known_label(cls, v: str) -> str:
        if v not in {"positive", "negative", "neutral"}:
            raise ValueError(f"unexpected label: {v}")
        return v

# parse the model's JSON; on ValidationError, re-prompt with the error text
data = Extraction.model_validate_json(raw_llm_json)
```
Prefer the provider's **native structured-output / tool-calling** mode over parsing free
text — it constrains generation instead of cleaning up after it. For a dedicated
framework, `guardrails-ai` adds validators + automatic re-asking; reach for it when you
need many reusable policies, not for a single schema.

## Layer 2 — policy
- **Input**: treat retrieved docs and user text as untrusted. Prompt-injection defense
  = keep instructions and data in separate roles/sections, and never let retrieved text
  silently become instructions.
- **Output**: validate before acting — no PII leakage, no off-topic answers, no unsafe
  content. For irreversible actions (sending mail, writing to a DB), gate behind a
  validated, typed result, not a raw string.

## The retry pattern (tie it together)
```
generate -> validate -> if invalid: re-prompt WITH the validation error -> repeat (max N)
```
Cap retries (`N`), and have a safe fallback when they're exhausted — don't loop forever
and don't ship the invalid output.

State which layer a given check belongs to, and prefer constraining generation over
post-hoc fixing wherever the provider supports it.
