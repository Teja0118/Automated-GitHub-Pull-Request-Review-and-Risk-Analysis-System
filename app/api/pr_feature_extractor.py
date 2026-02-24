from datetime import datetime, timedelta

from app.ingestion.github_client import GithubClient


class LivePRFeatureExtractor:
    def __init__(self, owner: str, repo: str):
        self.owner = owner
        self.repo = repo
        self.github = GithubClient()

    def _get_author_counts(self, author_login: str) -> tuple[int, int]:
        try:
            q_total = f"repo:{self.owner}/{self.repo} type:pr author:{author_login}"
            total = self.github.get("/search/issues", params={"q": q_total}).get("total_count", 0)

            since = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")
            q_recent = f"{q_total} created:>={since}"
            recent = self.github.get("/search/issues", params={"q": q_recent}).get("total_count", 0)

            return int(total), int(recent)
        except Exception:
            return 0, 0

    def extract_features(self, pr_number: int) -> dict:
        pr = self.github.get(f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}")

        files = list(self.github.paginate(f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/files"))

        total_files = len(files)
        total_additions = sum(f.get("additions", 0) for f in files)
        total_deletions = sum(f.get("deletions", 0) for f in files)
        code_churn = total_additions + total_deletions
        python_files_changed = sum(1 for f in files if f.get("filename", "").endswith(".py"))

        reviews = list(self.github.paginate(f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/reviews"))

        review_count = len(reviews)
        change_request_count = sum(1 for r in reviews if r.get("state") == "CHANGES_REQUESTED")
        commented_count = sum(1 for r in reviews if r.get("state") == "COMMENTED")
        has_reviews = 1 if review_count > 0 else 0

        created_at = pr.get("created_at")
        merged_at = pr.get("merged_at")
        if created_at and merged_at:
            created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            merged_dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
            time_to_merge_hours = (merged_dt - created_dt).total_seconds() / 3600
        else:
            time_to_merge_hours = 0

        author_login = pr.get("user", {}).get("login", "")
        author_pr_count, author_recent_prs = self._get_author_counts(author_login) if author_login else (0, 0)

        return {
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
            "author_pr_count": author_pr_count,
            "author_recent_prs": author_recent_prs,
        }
