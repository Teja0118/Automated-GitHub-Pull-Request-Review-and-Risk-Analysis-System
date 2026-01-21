from app.ingestion.github_client import GithubClient
from datetime import datetime

class LivePRFeatureExtractor:
    # To Extract ML Features for a single latest PR ar inference time

    def __init__(self, owner: str, repo: str):
        self.owner = owner
        self.repo = repo
        self.github = GithubClient()

    def extract_features(self, pr_number: int) -> dict:
        # Fetch PR metadata
        pr = self.github.get(
            f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}"
        )

        # Fetch PR files (diff stats)
        files = list(
            self.github.paginate(
                f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/files"
            )
        )

        total_files = len(files)
        total_additions = sum(f.get("additions", 0) for f in files)
        total_deletions = sum(f.get("deletions", 0) for f in files)
        code_churn = total_additions + total_deletions
        python_files_changed = sum(
            1 for f in files if f["filename"].endswith(".py")
        )

        # Fetch PR Reviews
        reviews = list(
            self.github.paginate(
                f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/reviews"
            )
        )

        review_count = len(reviews)
        change_request_count = sum(
            1 for r in reviews if r["state"] == "CHANGES_REQUESTED"
        )
        commented_count = sum(
            1 for r in reviews if r.get("body")
        )
        has_reviews = 1 if review_count > 0 else 0

        # Merge time feature
        created_at = pr.get("created_at")
        merged_at = pr.get("merged_at")
        if created_at and merged_at:
            created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            merged_dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))

            time_to_merge_hours = (
                merged_dt - created_dt
            ).total_seconds() / 3600
        else:
            time_to_merge_hours = 0

        # Author features
        author_pr_count = pr["author_association"] is not None
        author_recent_prs = 0

        # Feature vector
        features = {
            "total_files_changed": total_files,
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "code_churn": code_churn,
            "python_files_changed": python_files_changed,
            "review_count": review_count,
            "change_request_count": change_request_count,
            "commented_count": commented_count,
            "has_reviews": has_reviews,
            "time_to_merge_hours": time_to_merge_hours,
            "author_pr_count": int(author_pr_count),
            "author_recent_prs": author_recent_prs,
        }

        return features