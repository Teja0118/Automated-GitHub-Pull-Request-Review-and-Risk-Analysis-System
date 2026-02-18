from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import joblib
import os
import pandas as pd
from dotenv import load_dotenv
from typing import List

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

# Static & Templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

model = None


# UTIL 

def get_latest_pr_number() -> int:
    try:
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
            raise ValueError("No Pull Requests found.")

        return prs[0]["number"]

    except requests.exceptions.HTTPError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to fetch latest PR: {str(e)}")


def get_latest_pr_numbers(limit: int = 10) -> List[int]:
    prs = github_client.get(
        f"/repos/{REPO_OWNER}/{REPO_NAME}/pulls",
        params={
            "state": "open",
            "sort": "created",
            "direction": "desc",
            "per_page": limit,
        },
    )

    return [pr["number"] for pr in prs]


# STARTUP 

@app.on_event("startup")
def load_model():
    global model
    try:
        if not os.path.exists(MODEL_PATH):
            raise RuntimeError("Trained model not found.")

        model = joblib.load(MODEL_PATH)
        print("PR Risk model loaded successfully!")

    except Exception as e:
        raise RuntimeError(f"Failed to load ML model: {str(e)}")



# ENDPOINTS 

# UI Route
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


@app.get("/predict/pr/latest")
def predict_latest_pr():
    try:
        latest_pr_number = get_latest_pr_number()
        return predict_pr_risk(latest_pr_number)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



from fastapi import HTTPException
import requests

@app.get("/predict/pr/{pr_number}")
def predict_pr_risk(pr_number: int):
    try:
        # Feature extraction
        features = feature_extractor.extract_features(pr_number)

        # ML prediction
        df = pd.DataFrame([features])
        predicted_risk = model.predict(df)[0]
        probs = model.predict_proba(df)[0]

        risk_probabilities = {
            cls: float(prob)
            for cls, prob in zip(model.classes_, probs)
        }

        # AST analysis (non-blocking)
        try:
            ast_metrics = ast_analyzer.analyze_pr(pr_number)
        except Exception:
            ast_metrics = {"warning": "AST analysis failed"}

        # Explainability
        explanation = explainer.generate_explanation(
            predicted_risk=predicted_risk,
            features=features,
            ast_metrics=ast_metrics,
        )

        # LLM suggestions (non-blocking)
        try:
            llm_suggestions = llm.generate_suggestions(explanation)
        except Exception:
            llm_suggestions = "LLM suggestions currently unavailable."

        return {
            "pr_number": pr_number,
            "predicted_risk": predicted_risk,
            "risk_probabilities": risk_probabilities,
            "explanation": explanation,
            "llm_review_suggestions": llm_suggestions,
            "features_used": features,
            "ast_metrics": ast_metrics,
        }

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code

        if status == 404:
            raise HTTPException(status_code=404, detail="PR not found.")
        if status == 401:
            raise HTTPException(status_code=401, detail="Invalid GitHub token.")
        if status == 403:
            raise HTTPException(status_code=429, detail="GitHub API rate limit exceeded.")

        raise HTTPException(status_code=500, detail="GitHub API error.")

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected server error: {str(e)}"
        )



@app.get("/rank/prs")
def rank_latest_prs(limit: int = 5):
    if limit < 1 or limit > 10:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 10."
        )
    try:
        pr_numbers = get_latest_pr_numbers(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    ranked_results = []

    for pr_number in pr_numbers:
        try:
            features = feature_extractor.extract_features(pr_number)
            df = pd.DataFrame([features])

            prediction = model.predict(df)[0]
            probs = model.predict_proba(df)[0]

            risk_probs = {
                cls: float(prob)
                for cls, prob in zip(model.classes_, probs)
            }

            ranked_results.append({
                "pr_number": pr_number,
                "predicted_risk": prediction,
                "risk_probability": risk_probs[prediction],
                "risk_probabilities": risk_probs,
            })

        except Exception:
            # Skip failed PR instead of crashing entire ranking
            continue

    if not ranked_results:
        raise HTTPException(
            status_code=422,
            detail="Unable to rank PRs due to data extraction failures."
        )

    risk_priority = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    ranked_results.sort(
        key=lambda x: (risk_priority[x["predicted_risk"]], x["risk_probability"]),
        reverse=True,
    )

    return {
        "count": len(ranked_results),
        "ranked_pull_requests": ranked_results,
    }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
