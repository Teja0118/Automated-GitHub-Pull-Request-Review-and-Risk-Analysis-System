from typing import Dict, List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import PullRequest
from app.ingestion.github_client import GithubClient


class PullRequestIngestor:
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
        params = {"state": "all", "sort": "created", "direction": "asc"}

        for pr in self.github.paginate(endpoint, params=params, per_page=100):
            self._upsert_pull_request(pr)

        self.db.commit()

    def ingest_latest_pull_requests(self, limit: int = 100) -> List[int]:
        endpoint = f"/repos/{self.owner}/{self.repo}/pulls"
        params = {
            "state": "all",
            "sort": "updated",
            "direction": "desc",
        }

        pr_numbers: List[int] = []
        count = 0

        for pr in self.github.paginate(endpoint, params=params, per_page=100):
            self._upsert_pull_request(pr)
            pr_numbers.append(pr["number"])
            count += 1
            if count >= limit:
                break

        self.db.commit()
        return pr_numbers

    def _upsert_pull_request(self, pr: Dict) -> None:
        row = PullRequest(
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
            merged_at=pr["merged_at"],
        )

        try:
            self.db.merge(row)
        except IntegrityError:
            self.db.rollback()
