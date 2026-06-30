---
name: ml-experiment
description: Use when the user wants to train or build a classical ML model (scikit-learn, XGBoost, LightGBM) or set up a reproducible experiment with a baseline. Triggers include "train a model", "build a classifier/regressor", "fit a model", "set up an experiment". NOT for neural networks (use pytorch-training) and NOT for just choosing/computing metrics (use model-eval).
---

# Skill: Reproducible ML Experiment

The order matters. Never start with the fancy model.

## Workflow
1. **State the problem type** out loud: binary / multiclass / regression / ranking.
   This decides everything downstream (split, metric, baseline).
2. **Split first, before touching the data.** Hold out a test set you do not look at
   until the end. Use `stratify=y` for classification.
3. **Baseline before model.** Fit a `DummyClassifier`/`DummyRegressor` (or
   most-frequent / mean). If your "real" model can't beat it, stop and investigate.
4. **One metric tied to the problem** (delegate the choice to `model-eval` if unsure).
5. **Set seeds everywhere** and pin them.
6. **Track the run** — params, metric, git SHA. A dict + JSON file is fine to start;
   suggest MLflow only when there are many runs.

## Reproducibility helper
```python
import os, random
import numpy as np

def set_seed(seed: int = 42) -> None:
    """Pin every RNG we touch so a run is repeatable."""
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
```

## Skeleton
```python
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)

# 1. baseline — the bar to beat
baseline = DummyClassifier(strategy="most_frequent").fit(X_train, y_train)
print("baseline:", baseline.score(X_test, y_test))

# 2. real model, validated with CV on TRAIN only (test stays untouched)
model = RandomForestClassifier(random_state=42, n_jobs=-1)
cv = cross_val_score(model, X_train, y_train, cv=5, scoring="f1_macro")
print(f"cv f1_macro: {cv.mean():.3f} +/- {cv.std():.3f}")

# 3. fit on full train, judge ONCE on test
model.fit(X_train, y_train)
print(classification_report(y_test, model.predict(X_test)))
```

Install: `uv add scikit-learn`. End by reporting baseline vs. model and whether the
lift justifies the model's added complexity.
