from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True)
    github_repo_id = Column(BigInteger, unique=True)
    owner = Column(String(100))
    name = Column(String(100))
    full_name = Column(String(200), unique=True)
    html_url = Column(Text)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    fetched_at = Column(DateTime, server_default=func.now())


class PullRequest(Base):
    __tablename__ = "pull_requests"

    pr_id = Column(BigInteger, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"))

    pr_number = Column(Integer)
    state = Column(String(20))
    title = Column(Text)
    body = Column(Text)
    author_login = Column(String(100))

    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    closed_at = Column(DateTime)
    merged_at = Column(DateTime)

    commits_count = Column(Integer)
    additions = Column(Integer)
    deletions = Column(Integer)
    changed_files = Column(Integer)

    comments_count = Column(Integer)
    review_comments_count = Column(Integer)

    fetched_at = Column(DateTime, server_default=func.now())
    reviews_fetched = Column(Boolean, default=False)




class PRFile(Base):
    __tablename__ = "pr_files"

    id = Column(Integer, primary_key=True)
    pr_id = Column(BigInteger, ForeignKey("pull_requests.pr_id"))

    filename = Column(Text)
    status = Column(String(50))
    additions = Column(Integer)
    deletions = Column(Integer)
    changes = Column(Integer)
    patch = Column(Text)

class PRReview(Base):
    __tablename__ = "pr_reviews"

    review_id = Column(BigInteger, primary_key=True)
    pr_id = Column(BigInteger, ForeignKey("pull_requests.pr_id"))

    reviewer_login = Column(String(100))
    state = Column(String(50))
    body = Column(Text)
    submitted_at = Column(DateTime)


class RepositorySyncState(Base):
    __tablename__ = "repository_sync_state"

    repo_id = Column(Integer, ForeignKey("repositories.id"), primary_key=True)
    last_pr_sync_time = Column(DateTime, nullable=True)
    last_successful_fetch = Column(DateTime, nullable=True)

class PRDiffStats(Base):
    __tablename__ = "pr_diff_stats"

    pr_id = Column(BigInteger, ForeignKey("pull_requests.pr_id"), primary_key=True)

    total_files_changed = Column(Integer)
    total_additions = Column(Integer)
    total_deletions = Column(Integer)
    python_files_changed = Column(Integer)

    fetched_at = Column(DateTime, server_default=func.now())

class PRFeature(Base):
    __tablename__ = "pr_features"

    pr_id = Column(BigInteger, ForeignKey("pull_requests.pr_id"), primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"))

    # Diff / change features
    total_files_changed = Column(Integer)
    total_additions = Column(Integer)
    total_deletions = Column(Integer)
    code_churn = Column(Integer)
    python_files_changed = Column(Integer)

    # Temporal features
    pr_age_hours = Column(Integer)
    time_to_merge_hours = Column(Integer)
    merged = Column(Integer)  # 0 / 1

    # Review features
    review_count = Column(Integer)
    approval_count = Column(Integer)
    change_request_count = Column(Integer)
    commented_count = Column(Integer)
    has_reviews = Column(Integer)  # 0 / 1

    # Author history features
    author_pr_count = Column(Integer)
    author_recent_prs = Column(Integer)

    # Labels
    risk_label = Column(String(20), nullable=True)
    risk_score = Column(Integer, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
