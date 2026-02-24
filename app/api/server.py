from typing import Dict, List

import joblib
import os
import pandas as pd
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.api.pr_feature_extractor import LivePRFeatureExtractor
from app.db.models import Repository
from app.db.session import SessionLocal
from app.explainability.ast_analyzer import ASTAnalyzer
from app.explainability.risk_explainer import RiskExplainer
from app.ingestion.github_client import GithubClient
from app.llm.review_suggestor import LLMReviewSuggester
from app.main import run_pipeline
from app.ml.train_random_forest import train_random_forest

load_dotenv()

app = FastAPI(
    title="Automated GitHub PR Risk Analysis API",
    description="Predicts pull request risk and generates explainable review suggestions",
    version="2.0.0",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

github_client = GithubClient()
explainer = RiskExplainer()
llm = LLMReviewSuggester()
model_cache: Dict[str, object] = {}


class RepoRequest(BaseModel):
    owner: str = Field(..., min_length=1)
    repo: str = Field(..., min_length=1)


def model_path(owner: str, repo: str) -> str:
    owner_clean = owner.strip().replace("/", "_")
    repo_clean = repo.strip().replace("/", "_")
    return f"models/{owner_clean}__{repo_clean}.pkl"


def load_repo_model(owner: str, repo: str):
    path = model_path(owner, repo)

    if not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail=f"Model not found for {owner}/{repo}. Run /repos/train first.",
        )

    if path not in model_cache:
        model_cache[path] = joblib.load(path)
    return model_cache[path]


def get_repo_id(owner: str, repo: str) -> int:
    """
    Resolve repo_id using GitHub canonical repo id, then map to DB.
    Avoids owner/name casing or stale-text mismatches.
    """
    db = SessionLocal()
    try:
        owner = owner.strip()
        repo = repo.strip()

        repo_data = github_client.get(f"/repos/{owner}/{repo}")
        github_repo_id = repo_data["id"]

        row = (
            db.query(Repository)
            .filter(Repository.github_repo_id == github_repo_id)
            .first()
        )

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Repository {owner}/{repo} not found in DB. Run /repos/sync first.",
            )

        return row.id

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else 500
        if status == 404:
            raise HTTPException(status_code=404, detail="Repository not found on GitHub.")
        if status == 401:
            raise HTTPException(status_code=401, detail="Invalid GitHub token.")
        if status == 403:
            raise HTTPException(status_code=429, detail="GitHub API rate limit exceeded.")
        raise HTTPException(status_code=500, detail="GitHub API error while resolving repository.")
    finally:
        db.close()


def get_latest_pr_number(owner: str, repo: str) -> int:
    prs = github_client.get(
        f"/repos/{owner}/{repo}/pulls",
        params={
            "state": "all",
            "sort": "created",
            "direction": "desc",
            "per_page": 1,
        },
    )
    if not prs:
        raise HTTPException(status_code=404, detail="No pull requests found.")
    return prs[0]["number"]


def get_latest_pr_numbers(owner: str, repo: str, limit: int = 10) -> List[int]:
    prs = github_client.get(
        f"/repos/{owner}/{repo}/pulls",
        params={
            "state": "open",
            "sort": "created",
            "direction": "desc",
            "per_page": limit,
        },
    )
    return [pr["number"] for pr in prs]


def predict_single(owner: str, repo: str, pr_number: int):
    model = load_repo_model(owner, repo)
    feature_extractor = LivePRFeatureExtractor(owner, repo)
    ast_analyzer = ASTAnalyzer(owner, repo)

    features = feature_extractor.extract_features(pr_number)
    df = pd.DataFrame([features])

    predicted_risk = model.predict(df)[0]
    probs = model.predict_proba(df)[0]

    risk_probabilities = {
        cls: float(prob)
        for cls, prob in zip(model.classes_, probs)
    }

    try:
        ast_metrics = ast_analyzer.analyze_pr(pr_number)
    except Exception:
        ast_metrics = {"warning": "AST analysis failed"}

    explanation = explainer.generate_explanation(
        predicted_risk=predicted_risk,
        features=features,
        ast_metrics=ast_metrics,
    )

    try:
        llm_suggestions = llm.generate_suggestions(explanation)
    except Exception:
        llm_suggestions = "LLM suggestions currently unavailable."

    return {
        "repo": f"{owner}/{repo}",
        "pr_number": pr_number,
        "predicted_risk": predicted_risk,
        "risk_probabilities": risk_probabilities,
        "explanation": explanation,
        "llm_review_suggestions": llm_suggestions,
        "features_used": features,
        "ast_metrics": ast_metrics,
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/repos/sync")
def sync_repo(payload: RepoRequest):
    owner = payload.owner.strip()
    repo = payload.repo.strip()

    try:
        result = run_pipeline(owner, repo, max_prs=1000)
        return {
            "message": "Repository sync + feature build + labeling completed.",
            "repo_id": result["repo_id"],
            "repo": result["full_name"],
            "synced_prs": result.get("synced_prs", 0),
            "labeled_rows": result["labeled_rows"],
        }
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response else 500
        if code == 404:
            raise HTTPException(status_code=404, detail="Repository not found on GitHub.")
        if code == 401:
            raise HTTPException(status_code=401, detail="Invalid GitHub token.")
        if code == 403:
            raise HTTPException(status_code=429, detail="GitHub API rate limit exceeded.")
        raise HTTPException(status_code=500, detail="GitHub API error during sync.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/repos/train")
def train_repo_model(payload: RepoRequest):
    owner = payload.owner.strip()
    repo = payload.repo.strip()

    try:
        repo_id = get_repo_id(owner, repo)
        metrics = train_random_forest(repo_id, owner, repo)
        model_cache.pop(model_path(owner, repo), None)
        return {
            "message": "Model trained successfully.",
            "repo_id": repo_id,
            "repo": f"{owner}/{repo}",
            **metrics,
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/predict/{owner}/{repo}/pr/latest")
def predict_latest_pr(owner: str, repo: str):
    owner = owner.strip()
    repo = repo.strip()

    try:
        latest_pr_number = get_latest_pr_number(owner, repo)
        return predict_single(owner, repo, latest_pr_number)
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else 500
        if status == 404:
            raise HTTPException(status_code=404, detail="Repository or PR not found.")
        if status == 401:
            raise HTTPException(status_code=401, detail="Invalid GitHub token.")
        if status == 403:
            raise HTTPException(status_code=429, detail="GitHub API rate limit exceeded.")
        raise HTTPException(status_code=500, detail="GitHub API error.")


@app.get("/predict/{owner}/{repo}/pr/{pr_number}")
def predict_pr_risk(owner: str, repo: str, pr_number: int):
    owner = owner.strip()
    repo = repo.strip()

    try:
        return predict_single(owner, repo, pr_number)
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else 500
        if status == 404:
            raise HTTPException(status_code=404, detail="PR not found.")
        if status == 401:
            raise HTTPException(status_code=401, detail="Invalid GitHub token.")
        if status == 403:
            raise HTTPException(status_code=429, detail="GitHub API rate limit exceeded.")
        raise HTTPException(status_code=500, detail="GitHub API error.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {str(e)}")


@app.get("/rank/{owner}/{repo}/prs")
def rank_latest_prs(owner: str, repo: str, limit: int = 5):
    owner = owner.strip()
    repo = repo.strip()

    if limit < 1 or limit > 10:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 10.")

    try:
        pr_numbers = get_latest_pr_numbers(owner, repo, limit)
        model = load_repo_model(owner, repo)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    ranked_results = []
    feature_extractor = LivePRFeatureExtractor(owner, repo)

    for pr_number in pr_numbers:
        try:
            features = feature_extractor.extract_features(pr_number)
            df = pd.DataFrame([features])

            prediction = model.predict(df)[0]
            probs = model.predict_proba(df)[0]

            risk_probs = {cls: float(prob) for cls, prob in zip(model.classes_, probs)}

            ranked_results.append(
                {
                    "pr_number": pr_number,
                    "predicted_risk": prediction,
                    "risk_probability": risk_probs[prediction],
                    "risk_probabilities": risk_probs,
                }
            )
        except Exception:
            continue

    if not ranked_results:
        raise HTTPException(status_code=422, detail="Unable to rank PRs due to extraction failures.")

    risk_priority = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    ranked_results.sort(
        key=lambda x: (risk_priority[x["predicted_risk"]], x["risk_probability"]),
        reverse=True,
    )

    return {
        "repo": f"{owner}/{repo}",
        "count": len(ranked_results),
        "ranked_pull_requests": ranked_results,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
