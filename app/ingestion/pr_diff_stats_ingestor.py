from sqlalchemy.orm import Session

from app.db.models import PRDiffStats, PullRequest
from app.ingestion.github_client import GithubClient


class PRDiffStatsIngestor:
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

    def ingest_diff_stats(self) -> None:
        prs = (
            self.db_session.query(PullRequest)
            .filter(PullRequest.repo_id == self.repo_id)
            .all()
        )

        for pr in prs:
            self._ingest_single(pr)

        self.db_session.commit()

    def ingest_diff_stats_for_prs(self, pr_numbers: list[int]) -> None:
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
            files = list(
                self.github_client.paginate(
                    f"/repos/{self.owner}/{self.repo}/pulls/{pr.pr_number}/files"
                )
            )

            total_files_changed = len(files)
            total_additions = sum(f.get("additions", 0) for f in files)
            total_deletions = sum(f.get("deletions", 0) for f in files)
            python_files_changed = sum(
                1 for f in files if f.get("filename", "").endswith(".py")
            )

            row = PRDiffStats(
                pr_id=pr.pr_id,
                total_files_changed=total_files_changed,
                total_additions=total_additions,
                total_deletions=total_deletions,
                python_files_changed=python_files_changed,
            )
            self.db_session.merge(row)
        except Exception:
            pass
