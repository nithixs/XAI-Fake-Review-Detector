import os
import joblib

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "saved_model",
    "fake_review_model.pkl"
)

VECTORIZER_PATH = os.path.join(
    BASE_DIR,
    "saved_model",
    "tfidf_vectorizer.pkl"
)


model = joblib.load(
    MODEL_PATH
)

vectorizer = joblib.load(
    VECTORIZER_PATH
)


while True:

    review = input(
        "\nEnter product review (type exit to stop):\n"
    )

    if review.lower() == "exit":
        break

    review_vector = vectorizer.transform(
        [review]
    )

    prediction = model.predict(
        review_vector
    )[0]

    probabilities = model.predict_proba(
        review_vector
    )[0]

    genuine_probability = probabilities[0] * 100
    fake_probability = probabilities[1] * 100

    print("\n-----------------------------")

    if prediction == 1:
        print("Prediction : FAKE / SUSPICIOUS REVIEW")
    else:
        print("Prediction : GENUINE REVIEW")

    print(
        f"Fake Probability    : "
        f"{fake_probability:.2f}%"
    )

    print(
        f"Genuine Probability : "
        f"{genuine_probability:.2f}%"
    )

    print("-----------------------------")