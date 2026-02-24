from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.db.models import Repository, RepositorySyncState
from app.db.session import SessionLocal
from app.features.pr_feature_builder import PRFeatureBuilder
from app.ingestion.github_client import GithubClient
from app.ingestion.pr_diff_stats_ingestor import PRDiffStatsIngestor
from app.ingestion.pr_ingestor import PullRequestIngestor
from app.ingestion.pr_reviews_ingestor import PRReviewsIngestor
from app.ml.risk_labeler import RiskLabeler

load_dotenv()


def run_pipeline(owner: str, repo: str, max_prs: int = 200) -> dict:
    db: Session = SessionLocal()
    github = GithubClient()

    try:
        repo_data = github.get(f"/repos/{owner}/{repo}")

        repo_row = (
            db.query(Repository)
            .filter(Repository.github_repo_id == repo_data["id"])
            .first()
        )

        if not repo_row:
            repo_row = Repository(
                github_repo_id=repo_data["id"],
                owner=repo_data["owner"]["login"],
                name=repo_data["name"],
                full_name=repo_data["full_name"],
                html_url=repo_data["html_url"],
                created_at=repo_data["created_at"],
                updated_at=repo_data["updated_at"],
            )
            db.add(repo_row)
            db.commit()
            db.refresh(repo_row)

        sync_state = (
            db.query(RepositorySyncState)
            .filter(RepositorySyncState.repo_id == repo_row.id)
            .first()
        )

        if not sync_state:
            sync_state = RepositorySyncState(
                repo_id=repo_row.id,
                last_pr_sync_time=None,
                last_successful_fetch=None,
            )
            db.add(sync_state)
            db.commit()

        pr_ingestor = PullRequestIngestor(
            github_client=github,
            db_session=db,
            owner=owner,
            repo=repo,
            repo_id=repo_row.id,
        )
        pr_numbers = pr_ingestor.ingest_latest_pull_requests(limit=max_prs)

        diff_stats_ingestor = PRDiffStatsIngestor(
            github_client=github,
            db_session=db,
            owner=owner,
            repo=repo,
            repo_id=repo_row.id,
        )
        diff_stats_ingestor.ingest_diff_stats_for_prs(pr_numbers)

        pr_reviews_ingestor = PRReviewsIngestor(
            github_client=github,
            db_session=db,
            owner=owner,
            repo=repo,
            repo_id=repo_row.id,
        )
        pr_reviews_ingestor.ingest_reviews_for_prs(pr_numbers)

        feature_builder = PRFeatureBuilder(db)
        feature_builder.build_features(repo_id=repo_row.id)

        risk_labeler = RiskLabeler(db)
        labeled_count = risk_labeler.generate_labels(repo_id=repo_row.id)

        return {
            "repo_id": repo_row.id,
            "full_name": repo_row.full_name,
            "synced_prs": len(pr_numbers),
            "labeled_rows": labeled_count,
        }
    finally:
        db.close()


if __name__ == "__main__":
    result = run_pipeline("tiangolo", "fastapi", max_prs=100)
    print(result)
