from typing import Dict
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ingestion.github_client import GithubClient
from db.models import PullRequest


class PullRequestIngestor:
    """
    Ingest pull request metadata from GitHub into pull_requests table.
    GET /repos/{owner}/{repo}/pulls
    """

    def __init__(
        self,
        github_client: GithubClient,
        db_session: Session,
        owner: str,
        repo: str,
        repo_id: int,
    ):
        self.github = github_client
        self.db = db_session
        self.owner = owner
        self.repo = repo
        self.repo_id = repo_id

    def ingest_all_pull_requests(self) -> None:
        endpoint = f"/repos/{self.owner}/{self.repo}/pulls"
        params = {
            "state": "all",
            "sort": "created",
            "direction": "asc",
        }

        for pr in self.github.paginate(endpoint, params):
            self._upsert_pull_request(pr)

        self.db.commit()

    def _upsert_pull_request(self, pr: Dict) -> None:
        pr_record = PullRequest(
            pr_id=pr["id"],
            repo_id=self.repo_id,
            pr_number=pr["number"],
            state=pr["state"],
            title=pr["title"],
            body=pr["body"],
            author_login=pr["user"]["login"],
            created_at=pr["created_at"],
            updated_at=pr["updated_at"],
            closed_at=pr["closed_at"],
            merged_at=pr["merged_at"]
        )

        try:
            self.db.merge(pr_record)
        except IntegrityError:
            self.db.rollback()
