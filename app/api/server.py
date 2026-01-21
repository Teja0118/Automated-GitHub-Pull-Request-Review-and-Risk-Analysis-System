from fastapi import FastAPI
import joblib
import os
import pandas as pd
from app.ingestion.github_client import GithubClient
from app.api.pr_feature_extractor import LivePRFeatureExtractor
from dotenv import load_dotenv

load_dotenv()

MODEL_PATH = "models/pr_risk_model.pkl"

REPO_OWNER = os.getenv("REPO_OWNER")
REPO_NAME = os.getenv("REPO_NAME")

feature_extractor = LivePRFeatureExtractor(REPO_OWNER, REPO_NAME)

github_client = GithubClient()

def get_latest_pr_number() -> int:
    prs = github_client.get(
        f"/repos/{REPO_OWNER}/{REPO_NAME}/pulls",
        params={
            "state": "all",
            "sort": "created",
            "direction": "desc",
            "per_page": 1
        },
    )

    if not prs:
        raise ValueError("No Pull Requests found!")
    
    return prs[0]["number"]

app = FastAPI(
    title="Automated Github PR Risk Analysisi API",
    description="Predicts pull requests risk using ML",
    version="1.0.0",
)

model = None

@app.on_event("startup")
def load_model():
    global model
    
    if not os.path.exists(MODEL_PATH):
        raise RuntimeError("Trained model not found.")
    
    model = joblib.load(MODEL_PATH)
    print("PR Risk model loaded successfully!")

@app.get("/")
def health_check():
    return {
        "status": "OK",
        "message": "PR Risk Analysis API is running"
    }

@app.get("/predict/pr/latest")
def predict_latest_pr():
    latest_pr_number = get_latest_pr_number()
    return predict_pr_risk(latest_pr_number)

@app.get("/predict/pr/{pr_number}")
def predict_pr_risk(pr_number: int):
    features = feature_extractor.extract_features(pr_number)

    df = pd.DataFrame([features])

    prediction = model.predict(df)[0]

    probs = model.predict_proba(df)[0]
    classes = model.classes_

    risk_probabilities = {
        cls: float(prob)
        for cls, prob in zip(classes, probs)
    }

    return {
        "pr_number": pr_number,
        "predicted_risk": prediction,
        "risk_probabilities": risk_probabilities,
        "features_used": features,
    }
