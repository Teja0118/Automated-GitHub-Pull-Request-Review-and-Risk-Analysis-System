* Automated GitHub Pull Request Review and Risk Analysis System 
* Overview:

The Automated GitHub Pull Request Review and Risk Analysis System is an AI-driven platform that analyzes historical pull request data to predict risk levels, prioritize reviews, and generate explainable, intelligent review suggestions.

Unlike traditional rule-based tools, this system uses machine learning, AST-based code analysis, and LLMs to provide data-driven insights that help reviewers focus on high-risk pull requests and improve overall software quality.

* Problem Statement:

Traditional code review tools rely on static rules and lack data-driven prioritization of pull requests. As repositories scale, reviewers struggle to identify which pull requests need urgent attention.

* This project addresses that gap by:

Learning from historical pull request behavior

Predicting risk probabilistically

Explaining why a PR is risky

Generating AI-assisted review suggestions

* Solution Highlights:

ML-based PR risk prediction (LOW / MEDIUM / HIGH)

AST parsing for code complexity analysis

Explainable risk factors and reviewer focus areas

LLM-generated review suggestions

REST APIs + Web UI for real-time usage


* System Architecture:

GitHub API
   │
   ▼
Data Ingestion (PRs, Diffs, Reviews)
   │
   ▼
PostgreSQL (Structured Storage)
   │
   ▼
Feature Engineering + AST Parsing
   │
   ▼
ML Model (Random Forest)
   │
   ▼
Explainability Engine
   │
   ▼
LLM Review Generator (Groq API)
   │
   ▼
FastAPI Backend + Web UI

* Technologies Used:
Category-	Technologies
Language-	Python
Backend-	FastAPI
Database-	PostgreSQL
ML- Scikit-learn (Random Forest)
Feature Engineering-	Code diffs, AST parsing
AST Analysis-	Python ast module
LLM-	Groq API (LLaMA-based models)
UI-	FastAPI Templates (HTML/CSS)
ORM-	SQLAlchemy
Version Control-	Git, GitHub

* Project Structure:
app/
│
├── api/                 # FastAPI routes & server
├── ingestion/           # GitHub data ingestion
├── features/            # Feature builders & AST complexity
├── explainability/      # Risk explanations & AST analyzer
├── llm/                 # LLM-based review suggestions
├── ml/                  # Model training & risk labeling
├── db/                  # Database models & session
├── templates/           # UI templates
├── static/              # CSS / assets
│
├── main.py              # Data ingestion + feature pipeline
└── requirements.txt

* Features Extracted:

* Code Change Features:

Total files changed

Lines added / deleted

Code churn


Python file ratio


* AST-Based Complexity Features:

Number of functions

Number of classes

Branch count

Maximum nesting depth

Complexity flag (LOW / MEDIUM / HIGH)

Review Behavior Features:

Review count

Change requests

Comments

Approval count

* Developer History:

Total PRs by author

Recent PR activity

* Machine Learning:

Model: Random Forest Classifier

Labels: LOW, MEDIUM, HIGH

Training Data: Historical PR features

Evaluation: Accuracy, Precision, Recall, Confusion Matrix

Achieved Accuracy: ~95–98%

* Explainability:

Each prediction includes:

Risk summary

Key contributing factors

AST-based complexity insights

Reviewer focus areas

* LLM-Based Review Suggestions:

Uses Groq API (free, cloud-based)

No local model installation

* Generates:

Maintainability suggestions

Risk mitigation steps

Review recommendations

* API Endpoints:
Endpoint	    	    Description
/home	                Home page
/predict/pr/latest	    Predict risk for latest PR
/predict/pr/{pr_number}	Predict risk for specific PR
/rank/prs	Rank recent PRs by risk

* Web Interface:

Single-command run

* Displays:

Latest PR risk

PR-wise prediction

Ranked PR list

* Explanations & LLM suggestions

* How to Run:
1. Install dependencies:
pip install -r requirements.txt

2. Set environment variables (.env):
GROQ_API_KEY=your_groq_api_key
GITHUB_TOKEN=your_github_token
REPO_OWNER=tiangolo
REPO_NAME=fastapi

3. Run backend: 
uvicorn app.api.server:app --reload

4. Open browser:
http://127.0.0.1:8000

* Expected Outcome:

Accurate PR risk prediction

Prioritized review workflow

Explainable AI insights

Improved review efficiency

Reduced likelihood of risky merges
