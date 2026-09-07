import os
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)

# --------------------------------------------------
# 1. Paths
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_PATH = os.path.join(
    BASE_DIR,
    "dataset",
    "fake_reviews.csv"
)

MODEL_DIR = os.path.join(
    BASE_DIR,
    "saved_model"
)

os.makedirs(MODEL_DIR, exist_ok=True)


# --------------------------------------------------
# 2. Load Dataset
# --------------------------------------------------

df = pd.read_csv(DATA_PATH)

print("Dataset Shape:", df.shape)
print("\nColumns:")
print(df.columns)

print("\nLabel Distribution:")
print(df["label"].value_counts())


# --------------------------------------------------
# 3. Keep Required Columns
# --------------------------------------------------

df = df[["text_", "label"]]

df = df.dropna()

df["text_"] = df["text_"].astype(str)


# --------------------------------------------------
# 4. Convert Labels
#
# CG = Computer Generated = Fake = 1
# OR = Original Review    = Genuine = 0
# --------------------------------------------------

df["label"] = df["label"].map({
    "CG": 1,
    "OR": 0
})

df = df.dropna()

df["label"] = df["label"].astype(int)


# --------------------------------------------------
# 5. X and y
# --------------------------------------------------

X = df["text_"]
y = df["label"]


# --------------------------------------------------
# 6. Train Test Split
# --------------------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)

print("\nTraining Reviews:", len(X_train))
print("Testing Reviews :", len(X_test))


# --------------------------------------------------
# 7. TF-IDF
# --------------------------------------------------

vectorizer = TfidfVectorizer(
    lowercase=True,
    ngram_range=(1, 2),
    max_features=30000,
    min_df=2,
    sublinear_tf=True
)

X_train_tfidf = vectorizer.fit_transform(X_train)

X_test_tfidf = vectorizer.transform(X_test)

print("\nTF-IDF Shape:", X_train_tfidf.shape)


# --------------------------------------------------
# 8. Logistic Regression
# --------------------------------------------------

model = LogisticRegression(
    max_iter=1000,
    random_state=42
)

model.fit(
    X_train_tfidf,
    y_train
)


# --------------------------------------------------
# 9. Prediction
# --------------------------------------------------

y_pred = model.predict(X_test_tfidf)


# --------------------------------------------------
# 10. Evaluation
# --------------------------------------------------

accuracy = accuracy_score(
    y_test,
    y_pred
)

print("\n====================================")
print("       MODEL EVALUATION")
print("====================================")

print(f"\nAccuracy: {accuracy * 100:.2f}%")

print("\nClassification Report:")
print(
    classification_report(
        y_test,
        y_pred,
        target_names=[
            "Genuine",
            "Fake"
        ]
    )
)

print("\nConfusion Matrix:")
print(
    confusion_matrix(
        y_test,
        y_pred
    )
)
# --------------------------------------------------
# Save SHAP Background Data
# --------------------------------------------------

shap_background = X_train_tfidf[:200]

background_path = os.path.join(
    MODEL_DIR,
    "shap_background.pkl"
)

joblib.dump(
    shap_background,
    background_path
)

print("\nSHAP background saved successfully:")
print(background_path)


# --------------------------------------------------
# 11. Save Model
# --------------------------------------------------

model_path = os.path.join(
    MODEL_DIR,
    "fake_review_model.pkl"
)

vectorizer_path = os.path.join(
    MODEL_DIR,
    "tfidf_vectorizer.pkl"
)

joblib.dump(
    model,
    model_path
)

joblib.dump(
    vectorizer,
    vectorizer_path
)

print("\nModel saved successfully:")
print(model_path)

print("\nVectorizer saved successfully:")
print(vectorizer_path)