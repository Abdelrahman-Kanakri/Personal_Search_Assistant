---
name: eda
description: Use when the user wants to explore, profile, understand, or get a first look at a dataset before modeling. Triggers "explore this data", "EDA", "what's in this dataset", "profile the data", "look at the data first". Focuses on understanding; for transforming/cleaning use data-prep.
---

# Skill: Exploratory Data Analysis

Goal: understand the data and spot problems *before* modeling. Look, don't fix here.

## Checklist (in order)
1. **Shape & types** — rows, cols, dtypes. Wrong dtypes (numbers as strings, dates as
   objects) hide everything else.
2. **Missingness** — % missing per column. Is it random, or is missingness itself a
   signal?
3. **The target** — its distribution first. Class imbalance or a skewed/long-tailed
   regression target changes your whole metric/sampling strategy.
4. **Numeric features** — describe(), spot impossible values (negative age), heavy skew.
5. **Categorical features** — cardinality. A near-unique column is likely an ID, not a
   feature; a near-constant column is dead weight.
6. **Relationships** — feature ↔ target, and feature ↔ feature (multicollinearity).
7. **Leakage red flags** — any feature that's *too* predictive, or that couldn't exist
   at prediction time (e.g. `discharge_date` when predicting admission). Call these out
   loudly.

## Quick passes
```python
df.shape
df.info()
df.describe(include="all").T

# missingness, sorted
(df.isna().mean().sort_values(ascending=False) * 100).round(1)

# target
df[target].value_counts(normalize=True)          # classification
df[target].describe()                              # regression

# cardinality of object columns
df.select_dtypes("object").nunique().sort_values(ascending=False)

# numeric correlations (then eyeball |r| > ~0.8 pairs)
df.corr(numeric_only=True)
```

Install: `uv add pandas`. End EDA with a short written verdict: data quality issues,
likely-useful features, suspected leakage, and what to do in data-prep next.
Don't jump to modeling until these are answered.
