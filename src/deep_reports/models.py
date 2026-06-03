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
