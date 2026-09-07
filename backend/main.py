from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import os
import joblib
import shap

# ✅ DATABASE IMPORT - TOP LA ADD PANNANUM
from backend.database import (
    save_review,
    get_review_history,
    get_dashboard_stats
)


app = FastAPI(
    title="XAI Fake Review Detector",
    version="1.0"
)


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# --------------------------------------------------
# Paths
# --------------------------------------------------

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

MODEL_DIR = os.path.join(
    BASE_DIR,
    "ai_model",
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
# Load Model Files
# --------------------------------------------------

model = joblib.load(MODEL_PATH)
vectorizer = joblib.load(VECTORIZER_PATH)
background = joblib.load(BACKGROUND_PATH)


# --------------------------------------------------
# SHAP Explainer
# --------------------------------------------------

explainer = shap.LinearExplainer(
    model,
    background
)


# --------------------------------------------------
# Request Model
# --------------------------------------------------

class ReviewRequest(BaseModel):
    review: str


# --------------------------------------------------
# Home
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "XAI Fake Review Detection API is running"
    }


# --------------------------------------------------
# Predict
# --------------------------------------------------

@app.post("/predict")
def predict_review(request: ReviewRequest):

    review = request.review.strip()

    if not review:
        raise HTTPException(
            status_code=400,
            detail="Review cannot be empty"
        )


    # ----------------------------------------------
    # TF-IDF
    # ----------------------------------------------

    review_vector = vectorizer.transform(
        [review]
    )


    # ----------------------------------------------
    # Prediction
    # ----------------------------------------------

    prediction = model.predict(
        review_vector
    )[0]

    probabilities = model.predict_proba(
        review_vector
    )[0]


    genuine_probability = probabilities[0] * 100
    fake_probability = probabilities[1] * 100


    if prediction == 1:
        result = "Fake / Suspicious"
        confidence = fake_probability
    else:
        result = "Genuine"
        confidence = genuine_probability


    # ----------------------------------------------
    # SHAP Explanation
    # ----------------------------------------------

    shap_values = explainer.shap_values(
        review_vector
    )

    values = shap_values[0]

    feature_names = (
        vectorizer.get_feature_names_out()
    )

    present_indices = review_vector.indices

    explanation = []


    for index in present_indices:

        shap_value = float(
            values[index]
        )

        feature = feature_names[index]

        if shap_value > 0:
            influence = "Fake"
        else:
            influence = "Genuine"

        explanation.append({
            "feature": feature,
            "shap_value": round(
                shap_value,
                4
            ),
            "influence": influence
        })


    explanation.sort(
        key=lambda item:
        abs(item["shap_value"]),
        reverse=True
    )

    explanation = explanation[:10]


    # ==============================================
    # ✅ DATABASE SAVE - RETURN KU MUNNAADI ADD
    # ==============================================

    save_review(
        review=review,
        prediction=result,
        confidence=round(
            confidence,
            2
        ),
        fake_probability=round(
            fake_probability,
            2
        ),
        genuine_probability=round(
            genuine_probability,
            2
        )
    )


    # ----------------------------------------------
    # Response
    # ----------------------------------------------

    return {
        "review": review,

        "prediction": result,

        "confidence": round(
            confidence,
            2
        ),

        "fake_probability": round(
            fake_probability,
            2
        ),

        "genuine_probability": round(
            genuine_probability,
            2
        ),

        "explanation": explanation
    }


# ==================================================
# ✅ HISTORY ENDPOINT - predict function OUTSIDE
# ==================================================

@app.get("/history")
def history():
    return get_review_history(
        limit=20
    )


# ==================================================
# ✅ DASHBOARD STATS - predict function OUTSIDE
# ==================================================

@app.get("/stats")
def stats():
    return get_dashboard_stats()