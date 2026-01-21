import pandas as pd
import joblib

from sqlalchemy.orm import Session
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix

from app.db.session import SessionLocal
from app.db.models import PRFeature
import os

MODEL_PATH = "models/pr_risk_model.pkl"


def train_random_forest():
    db: Session = SessionLocal()

    # 1. Load features from DB
    features = db.query(PRFeature).all()

    if not features:
        print("No PR features found. Run Phase-2 and Phase-3 first.")
        return

    data = []
    for f in features:
        data.append({
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
        })

    df = pd.DataFrame(data)

    # 2. Split X and y
    X = df.drop(columns=["risk_label"])
    y = df["risk_label"]

    # 3. Train / Test split
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    # 4. Train Random Forest
    model = RandomForestClassifier(
        n_estimators=200,
        random_state=42,
        class_weight="balanced",
        n_jobs=-1,
    )

    model.fit(X_train, y_train)

    # 5. Evaluation
    y_pred = model.predict(X_test)

    print("\n=== Classification Report ===")
    print(classification_report(y_test, y_pred))

    print("\n=== Confusion Matrix ===")
    print(confusion_matrix(y_test, y_pred))

    # 6. Feature Importance
    feature_importance = pd.Series(
        model.feature_importances_,
        index=X.columns
    ).sort_values(ascending=False)

    print("\n=== Feature Importance ===")
    print(feature_importance)

    # 7. Save Model
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"\nModel saved to {MODEL_PATH}")

    db.close()


if __name__ == "__main__":
    train_random_forest()
