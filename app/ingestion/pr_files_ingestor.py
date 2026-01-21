from typing import Dict
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ingestion.github_client import GithubClient
from db.models import PullRequest, PRFile

class PRFilesIngestor:
    # To ingest pull request file-level changes from Github into pr_files table

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

    def ingest_files_for_all_prs(self) -> None:
        # Fetch and store files for all PRs present in the DB
        prs = self.db.query(PullRequest).all()

        for pr in prs:
            self._ingest_files_for_pr(pr)

        self.db.commit()

    def _ingest_files_for_pr(self, pr: PullRequest) -> None:
        # Fetch and store files for a single PR
        endpoint = f"/repos/{self.owner}/{self.repo}/pulls/{pr.pr_number}/files"

        for file_data in self.github.paginate(endpoint):
            self._ingest_pr_file(pr.pr_id, file_data)

    def _ingest_pr_file(self, pr_id: int, file_data: Dict) -> None:
        # Insert a single PR record
        pr_file = PRFile(
            pr_id = pr_id,
            filename=file_data["filename"],
            status=file_data["status"],
            additions=file_data["additions"],
            deletions=file_data["deletions"],
            changes=file_data["changes"],
            patch=file_data.get("patch")
        )

        try:
            self.db.add(pr_file)
        except IntegrityError:
            self.db.rollback()
