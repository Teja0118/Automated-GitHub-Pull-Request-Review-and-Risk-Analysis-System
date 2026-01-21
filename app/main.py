from db.session import SessionLocal
from db.models import Repository, RepositorySyncState

from ingestion.github_client import GithubClient
from ingestion.pr_ingestor import PullRequestIngestor
from ingestion.pr_diff_stats_ingestor import PRDiffStatsIngestor
from ingestion.pr_reviews_ingestor import PRReviewsIngestor
from features.pr_feature_builder import PRFeatureBuilder
from ml.risk_labeler import RiskLabeler


from dotenv import load_dotenv
import os

load_dotenv()

OWNER = "tiangolo"
REPO = "fastapi"


def main():
    
    # Data Collection Orchestration: 1. Repository metadata, 2. Pull request metadata, 3. PR files (diffs), 4. PR reviews

    db = SessionLocal()
    github = GithubClient()

    # 1. Repository metadata ingestion
    repo_data = github.get(f"/repos/{OWNER}/{REPO}")

    repo = (
        db.query(Repository)
        .filter(Repository.github_repo_id == repo_data["id"])
        .first()
    )

    if not repo:
        repo = Repository(
            github_repo_id=repo_data["id"],
            owner=repo_data["owner"]["login"],
            name=repo_data["name"],
            full_name=repo_data["full_name"],
            html_url=repo_data["html_url"],
            created_at=repo_data["created_at"],
            updated_at=repo_data["updated_at"],
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)

    # Initialize sync state if not exists
    sync_state = (
        db.query(RepositorySyncState)
        .filter(RepositorySyncState.repo_id == repo.id)
        .first()
    )

    if not sync_state:
        sync_state = RepositorySyncState(
            repo_id=repo.id,
            last_pr_sync_time=None,
            last_successful_fetch=None,
        )
        db.add(sync_state)
        db.commit()

    # 2. Pull Request metadata ingestion
    pr_ingestor = PullRequestIngestor(
        github_client=github,
        db_session=db,
        owner=OWNER,
        repo=REPO,
        repo_id=repo.id,
    )
    pr_ingestor.ingest_all_pull_requests()

    # 3. Aggregated PR diff stats ingestion
    diff_stats_ingestor = PRDiffStatsIngestor(
        github_client=github,
        db_session=db,
        owner=OWNER,
        repo=REPO,
    )
    diff_stats_ingestor.ingest_diff_stats()

    # 4. Pull Request reviews ingestion
    pr_reviews_ingestor = PRReviewsIngestor(
        github_client=github,
        db_session=db,
        owner=OWNER,
        repo=REPO,
    )
    pr_reviews_ingestor.ingest_reviews_for_all_prs()

    # Phase-2: Feature aggregation
    feature_builder = PRFeatureBuilder(db)
    feature_builder.build_features()

    # Phase-3: Risk labeling
    risk_labeler = RiskLabeler(db)
    risk_labeler.generate_labels()

    db.close()


if __name__ == "__main__":
    main()
