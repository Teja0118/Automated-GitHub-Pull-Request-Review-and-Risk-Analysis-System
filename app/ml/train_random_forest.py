import os

import joblib
import pandas as pd
from sqlalchemy.orm import Session
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

from app.db.models import PRFeature
from app.db.session import SessionLocal


def _model_path(owner: str, repo: str) -> str:
    owner_clean = owner.strip().replace("/", "_")
    repo_clean = repo.strip().replace("/", "_")
    return f"models/{owner_clean}__{repo_clean}.pkl"


def train_random_forest(repo_id: int, owner: str, repo: str) -> dict:
    db: Session = SessionLocal()

    try:
        features = db.query(PRFeature).filter(PRFeature.repo_id == repo_id).all()

        if not features:
            raise ValueError(f"No PR features found for repo_id={repo_id}. Run sync first.")

        data = []
        for f in features:
            if not f.risk_label:
                continue
            data.append(
                {
                    "total_files_changed": f.total_files_changed,
                    "total_additions": f.total_additions,
                    "total_deletions": f.total_deletions,
                    "code_churn": f.code_churn,
                    "python_files_changed": f.python_files_changed,
                    "review_count": f.review_count,
                    "change_request_count": f.change_request_count,
                    "commented_count": f.commented_count,
                    "has_reviews": f.has_reviews,
                    "time_to_merge_hours": f.time_to_merge_hours or 0,
                    "author_pr_count": f.author_pr_count,
                    "author_recent_prs": f.author_recent_prs,
                    "risk_label": f.risk_label,
                }
            )

        if len(data) < 20:
            raise ValueError("Not enough labeled rows to train reliably. Need at least 20.")

        df = pd.DataFrame(data)
        X = df.drop(columns=["risk_label"])
        y = df["risk_label"]

        if y.nunique() < 2:
            raise ValueError("Training labels have only one class. Need at least 2 classes.")

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        model = RandomForestClassifier(
            n_estimators=200,
            random_state=42,
            class_weight="balanced",
            n_jobs=-1,
        )
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        report = classification_report(y_test, y_pred, output_dict=True)
        matrix = confusion_matrix(y_test, y_pred).tolist()

        feature_importance = (
            pd.Series(model.feature_importances_, index=X.columns)
            .sort_values(ascending=False)
            .to_dict()
        )

        model_path = _model_path(owner, repo)
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(model, model_path)

        return {
            "model_path": model_path,
            "train_rows": len(X_train),
            "test_rows": len(X_test),
            "classes": list(model.classes_),
            "classification_report": report,
            "confusion_matrix": matrix,
            "feature_importance": feature_importance,
        }
    finally:
        db.close()


if __name__ == "__main__":
    # example
    print(train_random_forest(repo_id=1, owner="tiangolo", repo="fastapi"))
