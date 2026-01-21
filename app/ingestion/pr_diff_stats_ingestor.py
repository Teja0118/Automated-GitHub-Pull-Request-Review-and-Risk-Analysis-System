from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ingestion.github_client import GithubClient
from db.models import PullRequest, PRDiffStats


class PRDiffStatsIngestor:
    """
    Aggregates code diff statistics per PR using:
    GET /repos/{owner}/{repo}/pulls/{number}/files
    """

    def __init__(
        self,
        github_client: GithubClient,
        db_session: Session,
        owner: str,
        repo: str,
    ):
        self.github = github_client
        self.db = db_session
        self.owner = owner
        self.repo = repo

    def ingest_diff_stats(self, batch_size: int = 50) -> None:
        existing_count = self.db.query(PRDiffStats).count()
        if existing_count >= 1000:
            print("Diff stats already collected for 1000 PRs. Skipping.")
            return

        while True:
            prs = (
                self.db.query(PullRequest)
                .outerjoin(PRDiffStats, PRDiffStats.pr_id == PullRequest.pr_id)
                .filter(PRDiffStats.pr_id == None)
                .order_by(PullRequest.created_at.desc())
                .limit(batch_size)
                .all()
            )

            if not prs:
                break

            for pr in prs:
                self._process_single_pr(pr)

            self.db.commit()
            print(f"Committed diff stats for {len(prs)} PRs")


    def _process_single_pr(self, pr: PullRequest) -> None:
        endpoint = f"/repos/{self.owner}/{self.repo}/pulls/{pr.pr_number}/files"

        total_files = 0
        total_additions = 0
        total_deletions = 0
        python_files = 0

        for file_data in self.github.paginate(endpoint):
            total_files += 1
            total_additions += file_data.get("additions", 0)
            total_deletions += file_data.get("deletions", 0)

            if file_data["filename"].endswith(".py"):
                python_files += 1

        stats = PRDiffStats(
            pr_id=pr.pr_id,
            total_files_changed=total_files,
            total_additions=total_additions,
            total_deletions=total_deletions,
            python_files_changed=python_files,
        )

        try:
            self.db.add(stats)
        except IntegrityError:
            self.db.rollback()
