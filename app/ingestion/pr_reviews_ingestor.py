from typing import Dict
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from db.models import PRDiffStats
from ingestion.github_client import GithubClient
from db.models import PullRequest, PRReview


class PRReviewsIngestor:
    # To ingest pull request reviews from GitHub into the pr_reviews table.

    def __init__(
        self,
        github_client: GithubClient,
        db_session: Session,
        owner: str,
        repo: str
    ):
        self.github = github_client
        self.db = db_session
        self.owner = owner
        self.repo = repo



    def ingest_reviews_for_all_prs(self, batch_size: int = 50) -> None:
        while True:
            prs = (
                self.db.query(PullRequest)
                .join(PRDiffStats, PRDiffStats.pr_id == PullRequest.pr_id)
                .filter(PullRequest.reviews_fetched == False)
                .order_by(PullRequest.created_at.desc())
                .limit(batch_size)
                .all()
            )

            if not prs:
                break

            for pr in prs:
                self._ingest_reviews_for_pr(pr)
                pr.reviews_fetched = True
                self.db.add(pr)

            self.db.commit()
            print(f"Committed reviews for {len(prs)} PRs")

        print("All PR reviews fetched for PRs in pr_diff_stats")


    def _ingest_reviews_for_pr(self, pr: PullRequest) -> None:
         # Fetch and store reviews for a single PR.

        endpoint = f"/repos/{self.owner}/{self.repo}/pulls/{pr.pr_number}/reviews"

        for review in self.github.paginate(endpoint):
            self._insert_pr_review(pr.pr_id, review)

    def _insert_pr_review(self, pr_id: int, review: Dict) -> None:
        pr_review = PRReview(
            review_id=review["id"],
            pr_id=pr_id,
            reviewer_login=(
                review["user"]["login"]
                if review.get("user") is not None
                else "unknown"
            ),
            state=review["state"],
            body=review.get("body"),
            submitted_at=review["submitted_at"]
        )

        try:
            self.db.merge(pr_review)
        except IntegrityError:
            self.db.rollback()
