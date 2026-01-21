from sqlalchemy.orm import Session
from sqlalchemy import func

from db.models import PRFeature


class RiskLabeler:
    def __init__(self, db: Session):
        self.db = db

    def generate_labels(self) -> None:
        features = self.db.query(PRFeature).all()

        # compute raw risk scores first 
        scores = []

        max_churn = max(f.code_churn for f in features if f.code_churn is not None)
        max_merge_time = max((f.time_to_merge_hours or 0) for f in features)

        for f in features:
            churn_score = (f.code_churn / max_churn) if max_churn else 0
            merge_score = (
                (f.time_to_merge_hours / max_merge_time)
                if f.time_to_merge_hours and max_merge_time
                else 0
            )

            change_request_ratio = (
                f.change_request_count / f.review_count
                if f.review_count and f.review_count > 0
                else 0
            )

            no_review_penalty = 1 if f.has_reviews == 0 else 0

            risk_score = (
                0.4 * churn_score
                + 0.3 * change_request_ratio
                + 0.2 * merge_score
                + 0.1 * no_review_penalty
            )

            f.risk_score = risk_score
            scores.append(risk_score)

        # percentile thresholds
        scores_sorted = sorted(scores)
        low_cutoff = scores_sorted[int(0.60 * len(scores_sorted))]
        high_cutoff = scores_sorted[int(0.85 * len(scores_sorted))]

        # assign labels 
        for f in features:
            if f.risk_score <= low_cutoff:
                f.risk_label = "LOW"
            elif f.risk_score <= high_cutoff:
                f.risk_label = "MEDIUM"
            else:
                f.risk_label = "HIGH"

            f.risk_score = int(f.risk_score * 100)
            self.db.add(f)

        self.db.commit()
        print("Risk labels generated using percentile-based thresholds")

