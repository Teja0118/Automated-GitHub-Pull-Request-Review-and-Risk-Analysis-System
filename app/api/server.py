from fastapi import FastAPI
import joblib
import os
import pandas as pd
from dotenv import load_dotenv

from app.ingestion.github_client import GithubClient
from app.api.pr_feature_extractor import LivePRFeatureExtractor
from app.explainability.risk_explainer import RiskExplainer
from app.explainability.ast_analyzer import ASTAnalyzer
from app.llm.review_suggestor import LLMReviewSuggester

load_dotenv()

# CONFIG 

MODEL_PATH = "models/pr_risk_model.pkl"

REPO_OWNER = os.getenv("REPO_OWNER")
REPO_NAME = os.getenv("REPO_NAME")

if not REPO_OWNER or not REPO_NAME:
    raise RuntimeError("REPO_OWNER and REPO_NAME must be set in .env")

# INITIALIZE 

github_client = GithubClient()

feature_extractor = LivePRFeatureExtractor(REPO_OWNER, REPO_NAME)
explainer = RiskExplainer()
ast_analyzer = ASTAnalyzer(REPO_OWNER, REPO_NAME)
llm = LLMReviewSuggester()

app = FastAPI(
    title="Automated GitHub PR Risk Analysis API",
    description="Predicts pull request risk and generates explainable review suggestions",
    version="1.0.0",
)

model = None


# UTIL 

def get_latest_pr_number() -> int:
    prs = github_client.get(
        f"/repos/{REPO_OWNER}/{REPO_NAME}/pulls",
        params={
            "state": "all",
            "sort": "created",
            "direction": "desc",
            "per_page": 1,
        },
    )

    if not prs:
        raise ValueError("No Pull Requests found!")

    return prs[0]["number"]


# STARTUP 

@app.on_event("startup")
def load_model():
    global model

    if not os.path.exists(MODEL_PATH):
        raise RuntimeError("Trained model not found.")

    model = joblib.load(MODEL_PATH)
    print("PR Risk model loaded successfully!")


# ENDPOINTS 

@app.get("/")
def health_check():
    return {
        "status": "OK",
        "message": "PR Risk Analysis API is running",
    }


@app.get("/predict/pr/latest")
def predict_latest_pr():
    latest_pr_number = get_latest_pr_number()
    return predict_pr_risk(latest_pr_number)


@app.get("/predict/pr/{pr_number}")
def predict_pr_risk(pr_number: int):
    # 1. Feature extraction
    features = feature_extractor.extract_features(pr_number)
    df = pd.DataFrame([features])

    # 2. ML prediction
    predicted_risk = model.predict(df)[0]
    probs = model.predict_proba(df)[0]
    classes = model.classes_

    risk_probabilities = {
        cls: float(prob)
        for cls, prob in zip(classes, probs)
    }

    # 3. AST analysis
    ast_metrics = ast_analyzer.analyze_pr(pr_number)

    # 4. Explainability
    explanation = explainer.generate_explanation(
        predicted_risk=predicted_risk,
        features=features,
        ast_metrics=ast_metrics,
    )

    # 5. LLM suggestions
    llm_suggestions = llm.generate_suggestions(explanation)

    return {
        "pr_number": pr_number,
        "predicted_risk": predicted_risk,
        "risk_probabilities": risk_probabilities,
        "explanation": explanation,
        "llm_review_suggestions": llm_suggestions,
        "features_used": features,
        "ast_metrics": ast_metrics,
    }
