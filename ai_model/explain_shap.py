import os
import joblib
import shap
import numpy as np
import matplotlib.pyplot as plt


# --------------------------------------------------
# Paths
# --------------------------------------------------

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

MODEL_DIR = os.path.join(
    BASE_DIR,
    "saved_model"
)

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "fake_review_model.pkl"
)

VECTORIZER_PATH = os.path.join(
    MODEL_DIR,
    "tfidf_vectorizer.pkl"
)

BACKGROUND_PATH = os.path.join(
    MODEL_DIR,
    "shap_background.pkl"
)


# --------------------------------------------------
# Load Files
# --------------------------------------------------

model = joblib.load(
    MODEL_PATH
)

vectorizer = joblib.load(
    VECTORIZER_PATH
)

background = joblib.load(
    BACKGROUND_PATH
)


# --------------------------------------------------
# User Input
# --------------------------------------------------

review = input(
    "\nEnter review to explain:\n"
)


# --------------------------------------------------
# Convert Review to TF-IDF
# --------------------------------------------------

review_vector = vectorizer.transform(
    [review]
)


# --------------------------------------------------
# Prediction
# --------------------------------------------------

prediction = model.predict(
    review_vector
)[0]

probabilities = model.predict_proba(
    review_vector
)[0]

genuine_probability = probabilities[0] * 100
fake_probability = probabilities[1] * 100


print("\n====================================")
print("            AI PREDICTION")
print("====================================")

if prediction == 1:
    print("Prediction: FAKE / SUSPICIOUS")
else:
    print("Prediction: GENUINE")

print(
    f"Fake Probability    : "
    f"{fake_probability:.2f}%"
)

print(
    f"Genuine Probability : "
    f"{genuine_probability:.2f}%"
)


# --------------------------------------------------
# SHAP Linear Explainer
# --------------------------------------------------

explainer = shap.LinearExplainer(
    model,
    background
)

shap_values = explainer.shap_values(
    review_vector
)


# --------------------------------------------------
# Feature Names
# --------------------------------------------------

feature_names = (
    vectorizer
    .get_feature_names_out()
)


# SHAP values for current review
values = shap_values[0]


# TF-IDF values of current review
review_dense = (
    review_vector
    .toarray()[0]
)


# Find only words actually present
present_indices = np.where(
    review_dense > 0
)[0]


# --------------------------------------------------
# Get Important Features
# --------------------------------------------------

important_features = []

for index in present_indices:

    word = feature_names[index]

    shap_value = values[index]

    tfidf_value = review_dense[index]

    important_features.append(
        (
            word,
            shap_value,
            tfidf_value
        )
    )


# Sort using absolute SHAP importance
important_features.sort(
    key=lambda x: abs(x[1]),
    reverse=True
)


# Top 15
top_features = important_features[:15]


# --------------------------------------------------
# Print Explanation
# --------------------------------------------------

print("\n====================================")
print("          SHAP EXPLANATION")
print("====================================")

print(
    "\nPositive SHAP → pushes toward FAKE"
)

print(
    "Negative SHAP → pushes toward GENUINE\n"
)


for word, shap_value, tfidf_value in top_features:

    if shap_value > 0:
        direction = "FAKE"
    else:
        direction = "GENUINE"

    print(
        f"{word:<25} "
        f"{shap_value:+.4f} "
        f"→ {direction}"
    )


# --------------------------------------------------
# Plot
# --------------------------------------------------

if len(top_features) > 0:

    words = [
        item[0]
        for item in reversed(top_features)
    ]

    contributions = [
        item[1]
        for item in reversed(top_features)
    ]

    plt.figure(
        figsize=(10, 6)
    )

    plt.barh(
        words,
        contributions
    )

    plt.axvline(
        x=0,
        linewidth=1
    )

    plt.xlabel(
        "SHAP Contribution"
    )

    plt.ylabel(
        "Words / Phrases"
    )

    plt.title(
        "Why did the AI make this prediction?"
    )

    plt.tight_layout()


    output_path = os.path.join(
        BASE_DIR,
        "shap_explanation.png"
    )

    plt.savefig(
        output_path,
        dpi=200,
        bbox_inches="tight"
    )

    print(
        "\nSHAP graph saved:"
    )

    print(
        output_path
    )

    plt.show()

else:

    print(
        "\nNo known TF-IDF features "
        "were found in this review."
    )