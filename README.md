# Automated GitHub Pull Request Review and Risk Analysis System

## Overview

The Automated GitHub Pull Request Review and Risk Analysis System is an AI-driven platform that analyzes pull request data to predict risk levels, prioritize reviews, and generate explainable, intelligent review suggestions.

Unlike traditional rule-based tools, this system uses machine learning, AST-based code analysis, and LLMs to provide data-driven insights that help reviewers focus on high-risk pull requests and improve overall software quality.

## Problem Statement

Traditional code review tools rely on static rules and lack data-driven prioritization of pull requests. As repositories scale, reviewers struggle to identify which pull requests need urgent attention.

This project addresses that gap by:
- Learning from pull request behavior
- Predicting risk probabilistically
- Explaining why a PR is risky
- Generating AI-assisted review suggestions

## Solution Highlights

- ML-based PR risk prediction (`LOW` / `MEDIUM` / `HIGH`)
- AST parsing for code complexity analysis
- Explainable risk factors and reviewer focus areas
- LLM-generated review suggestions
- REST APIs + Web UI for real-time usage
- Dynamic multi-repo support (user selects any repository)

---

## System Architecture

GitHub API  
-> Data Ingestion (PRs, Diffs, Reviews)  
-> PostgreSQL (Structured Storage)  
-> Feature Engineering + AST Parsing  
-> ML Model (Random Forest)  
-> Explainability Engine  
-> LLM Review Generator (Groq API)  
-> FastAPI Backend + Web UI

---

## Technologies Used

- Language: Python
- Backend: FastAPI
- Database: PostgreSQL
- ORM: SQLAlchemy
- ML: Scikit-learn (Random Forest)
- Feature Engineering: Code diffs, review metadata, temporal and author signals
- AST Analysis: Python `ast` module
- LLM: Groq API (LLaMA-based models)
- UI: FastAPI templates (HTML/CSS)
- Version Control: Git, GitHub

---

## Project Structure

```text
app/
├── api/                 # FastAPI routes & server
├── ingestion/           # GitHub data ingestion
├── features/            # Feature builders & AST complexity
├── explainability/      # Risk explanations & AST analyzer
├── llm/                 # LLM-based review suggestions
├── ml/                  # Model training & risk labeling
├── db/                  # Database models & session
├── templates/           # UI templates
├── static/              # CSS / assets
└── main.py              # Data ingestion + feature + labeling pipeline

models/
└── {owner}__{repo}.pkl  # Repo-specific trained model files
```

---

## Features Used for ML

- Code change features:
  - `total_files_changed`
  - `total_additions`
  - `total_deletions`
  - `code_churn`
  - `python_files_changed`

- Review behavior features:
  - `review_count`
  - `change_request_count`
  - `commented_count`
  - `has_reviews`

- Temporal features:
  - `time_to_merge_hours`

- Author activity features:
  - `author_pr_count`
  - `author_recent_prs`

---

## Explainability Output

Each prediction includes:
- Risk summary
- Probabilities for each class
- AST-based complexity insight
- Reviewer focus guidance
- LLM-generated review suggestions

---

## API Endpoints

### UI
- `GET /`
  - Opens the web interface.

### Repository Sync and Training
- `POST /repos/sync`
  - Request body:
    ```json
    {
      "owner": "tiangolo",
      "repo": "fastapi"
    }
    ```
  - Action: Ingests PR metadata, diff stats, reviews, builds features, and generates risk labels for selected repository.

- `POST /repos/train`
  - Request body:
    ```json
    {
      "owner": "tiangolo",
      "repo": "fastapi"
    }
    ```
  - Action: Trains Random Forest model from stored DB features for selected repository.

### Prediction
- `GET /predict/{owner}/{repo}/pr/latest`
  - Predicts risk for latest PR in selected repository.

- `GET /predict/{owner}/{repo}/pr/{pr_number}`
  - Predicts risk for a specific PR number.

### Ranking
- `GET /rank/{owner}/{repo}/prs?limit=5`
  - Ranks latest open PRs by predicted risk.
  - `limit` must be between `1` and `10`.

---

## Environment Variables

Create a `.env` file:

```env
# GitHub access token
GITHUB_TOKEN=your_github_token
# alternatively:
# GITHUB_API_TOKEN=your_github_token

# Groq API key
GROQ_API_KEY=your_groq_api_key

# Database config
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_db_name
```

---

## Installation and Run

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start backend:
```bash
uvicorn app.api.server:app --reload
```

3. Open browser:
- `http://127.0.0.1:8000`

---

## Recommended Usage Flow (UI)

1. Enter repository owner and repo.
2. Click **Sync Repo Data**.
3. Click **Train Repo Model**.
4. Use:
   - **Analyze Latest PR**
   - **Analyze PR**
   - **Rank Latest PRs**

---

## Notes

- Model files are stored per repo:
  - `models/{owner}__{repo}.pkl`
- You must run sync and train before prediction for a new repository.
- Predictions combine:
  - ML score
  - AST analysis
  - LLM review suggestions

---

## Expected Outcome

- Accurate PR risk prediction
- Prioritized review workflow
- Explainable AI insights for reviewers
- Improved code review efficiency
- Reduced likelihood of risky merges
```