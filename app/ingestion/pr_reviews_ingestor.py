from sqlalchemy.orm import Session

from app.db.models import PRReview, PullRequest
from app.ingestion.github_client import GithubClient


class PRReviewsIngestor:
    def __init__(
        self,
        github_client: GithubClient,
        db_session: Session,
        owner: str,
        repo: str,
        repo_id: int,
    ):
        self.github_client = github_client
        self.db_session = db_session
        self.owner = owner
        self.repo = repo
        self.repo_id = repo_id

    def ingest_reviews_for_all_prs(self) -> None:
        prs = (
            self.db_session.query(PullRequest)
            .filter(PullRequest.repo_id == self.repo_id)
            .all()
        )

        for pr in prs:
            self._ingest_single(pr)

        self.db_session.commit()

    def ingest_reviews_for_prs(self, pr_numbers: list[int]) -> None:
        if not pr_numbers:
            return

        prs = (
            self.db_session.query(PullRequest)
            .filter(
                PullRequest.repo_id == self.repo_id,
                PullRequest.pr_number.in_(pr_numbers),
            )
            .all()
        )

        for pr in prs:
            self._ingest_single(pr)

        self.db_session.commit()

    def _ingest_single(self, pr: PullRequest) -> None:
        try:
            reviews = list(
                self.github_client.paginate(
                    f"/repos/{self.owner}/{self.repo}/pulls/{pr.pr_number}/reviews"
                )
            )

            for rv in reviews:
                row = PRReview(
                    review_id=rv["id"],
                    pr_id=pr.pr_id,
                    reviewer_login=(rv.get("user") or {}).get("login"),
                    state=rv.get("state"),
                    body=rv.get("body"),
                    submitted_at=rv.get("submitted_at"),
                )
                self.db_session.merge(row)

            pr.reviews_fetched = True
            self.db_session.add(pr)
        except Exception:
            pass
