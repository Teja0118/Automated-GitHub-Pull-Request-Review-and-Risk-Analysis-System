from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from db.models import (
    PullRequest,
    PRDiffStats,
    PRReview,
    PRFeature,
)


class PRFeatureBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build_features(self) -> None:
        
        # Populate pr_features table for PRs present in pr_diff_stats
        prs = (
            self.db.query(PullRequest, PRDiffStats)
            .join(PRDiffStats, PRDiffStats.pr_id == PullRequest.pr_id)
            .all()
        )

        for pr, diff in prs:
            self._build_single_pr_feature(pr, diff)

        self.db.commit()
        print(f"Inserted/updated {len(prs)} PR feature rows")

    def _build_single_pr_feature(self, pr: PullRequest, diff: PRDiffStats) -> None:
        # ---- Temporal features ----
        created_at = pr.created_at
        closed_at = pr.closed_at or datetime.utcnow()
        merged = 1 if pr.merged_at else 0

        pr_age_hours = int((closed_at - created_at).total_seconds() / 3600)

        time_to_merge_hours = (
            int((pr.merged_at - created_at).total_seconds() / 3600)
            if pr.merged_at
            else None
        )

        # Review features
        reviews = (
            self.db.query(PRReview)
            .filter(PRReview.pr_id == pr.pr_id)
            .all()
        )

        review_count = len(reviews)
        approval_count = sum(1 for r in reviews if r.state == "APPROVED")
        change_request_count = sum(1 for r in reviews if r.state == "CHANGES_REQUESTED")
        commented_count = sum(1 for r in reviews if r.state == "COMMENTED")
        has_reviews = 1 if review_count > 0 else 0

        # Author history features
        author_pr_count = (
            self.db.query(func.count(PullRequest.pr_id))
            .filter(PullRequest.author_login == pr.author_login)
            .scalar()
        )

        ninety_days_ago = created_at - timedelta(days=90)

        author_recent_prs = (
            self.db.query(func.count(PullRequest.pr_id))
            .filter(
                PullRequest.author_login == pr.author_login,
                PullRequest.created_at >= ninety_days_ago,
            )
            .scalar()
        )

        # Build feature row
        feature = PRFeature(
            pr_id=pr.pr_id,
            repo_id=pr.repo_id,

            total_files_changed=diff.total_files_changed,
            total_additions=diff.total_additions,
            total_deletions=diff.total_deletions,
            code_churn=diff.total_additions + diff.total_deletions,
            python_files_changed=diff.python_files_changed,

            pr_age_hours=pr_age_hours,
            time_to_merge_hours=time_to_merge_hours,
            merged=merged,

            review_count=review_count,
            approval_count=approval_count,
            change_request_count=change_request_count,
            commented_count=commented_count,
            has_reviews=has_reviews,

            author_pr_count=author_pr_count,
            author_recent_prs=author_recent_prs,
        )

        self.db.merge(feature)
