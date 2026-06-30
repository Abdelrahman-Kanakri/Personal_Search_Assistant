---
name: model-eval
description: Use when the user wants to evaluate a trained model, choose the right metric, set up cross-validation, interpret results, or diagnose overfitting/leakage. Triggers "evaluate the model", "which metric should I use", "is this overfitting", "cross-validation", "why is my accuracy so high". Applies to both classical ML and deep learning.
---

# Skill: Model Evaluation

A number means nothing without the right metric and an honest validation split.

## 1. Pick the metric from the problem
- **Balanced classification** → accuracy is fine, but still report precision/recall.
- **Imbalanced classification** → accuracy lies. Use F1 (macro for multiclass),
  PR-AUC, or recall@fixed-precision depending on which error costs more.
- **Ranking/retrieval** → MAP, NDCG, recall@k.
- **Regression** → MAE (robust, interpretable), RMSE (punishes big errors), R²
  (variance explained). Report MAE + RMSE together; the gap tells you about outliers.
- Always state *why* this metric matches the business/error cost.

## 2. Validation strategy
- Default classification: **StratifiedKFold** (preserves class ratios).
- **Temporal data → TimeSeriesSplit.** Random splits leak the future into the past.
- **Grouped data** (multiple rows per user/patient) → **GroupKFold**, or the same
  group lands in train and test and your score is fake.

## 3. The "too good to be true" checklist
If a metric looks suspiciously high, suspect leakage first:
- A feature that wouldn't exist at prediction time.
- A transform fit on the full dataset (see data-prep).
- Duplicate/near-duplicate rows split across train and test.
- The target encoded into a feature (e.g. an ID correlated with the label).

## 4. Overfitting vs. underfitting
- **train ≫ val** → overfitting: regularize, more data, simpler model.
- **train ≈ val and both poor** → underfitting/bug: more capacity, better features,
  or check the data pipeline.

## Snippet
```python
from sklearn.model_selection import StratifiedKFold, cross_validate

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
scores = cross_validate(
    full_pipeline, X_train, y_train, cv=cv,
    scoring=["f1_macro", "roc_auc"], return_train_score=True,
)
# compare train vs test scores per fold to see the overfitting gap
```

Report the metric with its spread across folds (`mean +/- std`), not a single number.
