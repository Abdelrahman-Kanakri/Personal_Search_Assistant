---
name: data-prep
description: Use when the user wants to clean, preprocess, transform, encode, scale, impute, or build a feature pipeline for a dataset. Triggers "clean this data", "preprocess", "encode the categoricals", "scale the features", "build a pipeline". For just looking at the data use eda.
---

# Skill: Data Cleaning & Preprocessing (leakage-safe)

The cardinal rule: **fit transforms on TRAIN only, then apply to val/test.** Fitting a
scaler or imputer on the full dataset leaks test statistics into training and inflates
your scores. Always split first.

## Workflow
1. **Split before any fitting.**
2. Decide per column: drop / impute / encode / scale.
3. Put it all in a `Pipeline` / `ColumnTransformer` so the *same fitted* transform
   carries to test and to production — no manual re-doing.
4. Handle outliers deliberately (clip, log-transform, or leave) — and say why.
5. Persist the fitted pipeline (`joblib.dump`) so inference matches training exactly.

## Skeleton — one fitted object, no leakage
```python
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)

num_cols = X_train.select_dtypes("number").columns
cat_cols = X_train.select_dtypes("object").columns

numeric = Pipeline([
    ("impute", SimpleImputer(strategy="median")),
    ("scale", StandardScaler()),
])
categorical = Pipeline([
    ("impute", SimpleImputer(strategy="most_frequent")),
    ("encode", OneHotEncoder(handle_unknown="ignore")),
])

preprocess = ColumnTransformer([
    ("num", numeric, num_cols),
    ("cat", categorical, cat_cols),
])

# fit on TRAIN only; transform both
X_train_t = preprocess.fit_transform(X_train)
X_test_t = preprocess.transform(X_test)          # NOT fit_transform
```

Then bolt your model on as a final pipeline step so cross-validation re-fits the
preprocessing inside each fold (the only fully leak-free way to CV):
```python
full = Pipeline([("prep", preprocess), ("model", model)])
```

Install: `uv add scikit-learn joblib`. Flag any transform you were tempted to fit on
the whole dataset — that's the most common silent bug in this step.
