from pydantic import BaseModel, Field


class RepoFile(BaseModel):
    path: str
    size: int
    content: str = ""
    reason: str = ""


class RepoInspection(BaseModel):
    repo_url: str
    repo_name: str
    commit_sha: str = ""
    readme: str = ""
    manifests: dict[str, str] = Field(default_factory=dict)
    file_tree: list[str] = Field(default_factory=list)
    entry_files: list[str] = Field(default_factory=list)
    key_files: list[RepoFile] = Field(default_factory=list)
    skipped_reason: str = ""


class SourcePackage(BaseModel):
    repo_url: str
    repo_name: str
    commit_sha: str = ""
    readme_excerpt: str = ""
    tech_stack: dict = Field(default_factory=dict)
    file_tree_summary: str = ""
    entry_files: list[str] = Field(default_factory=list)
    key_files: list[RepoFile] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)


class DeepReportCandidate(BaseModel):
    repo_url: str
    repo_name: str
    article_id: int | None = None
    source_id: str = ""
    source_detail: str = ""
    title: str = ""
    summary: str = ""
    reviewer_score: int = 0
    candidate_score: int = 0
    trigger_reason: str = ""
    metadata: dict = Field(default_factory=dict)
