from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class FlowStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str
    description: str


class DeepReportFlow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prerequisites: list[str]
    steps: list[FlowStep] = Field(min_length=3, max_length=8)

    @model_validator(mode="after")
    def validate_unique_step_ids(self):
        step_ids = [step.id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("flow step ids must be unique")
        return self


class DeepReportQuickStart(DeepReportFlow):
    expected_result: str


class DeepReportDeployment(DeepReportFlow):
    operations: list[str]


class DeepReportDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: str
    reasons: list[str]
    best_for: list[str]
    not_for: list[str]


class ArchitectureNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str
    role: str
    group: str | None


class ArchitectureEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    label: str


class DeepReportArchitecture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern: str
    summary: str
    nodes: list[ArchitectureNode] = Field(min_length=4, max_length=10)
    edges: list[ArchitectureEdge]

    @model_validator(mode="after")
    def validate_graph(self):
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("architecture node ids must be unique")

        known_node_ids = set(node_ids)
        for edge in self.edges:
            if edge.source not in known_node_ids or edge.target not in known_node_ids:
                raise ValueError("architecture edges must reference existing nodes")
            if edge.source == edge.target:
                raise ValueError("architecture edges must not contain self-loops")
        return self


class CoreModule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    responsibility: str
    depends_on: list[str]


class DeepReportEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    reason: str


class DeepReportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str
    tech_stack: list[str]
    use_cases: list[str]
    decision: DeepReportDecision
    architecture: DeepReportArchitecture
    quick_start: DeepReportQuickStart
    deployment: DeepReportDeployment
    core_modules: list[CoreModule]
    runtime_data_flow: list[FlowStep] = Field(min_length=3, max_length=8)
    strengths: list[str]
    limitations: list[str]
    actionable_takeaways: list[str]
    source_evidence: list[DeepReportEvidence]

    @model_validator(mode="after")
    def validate_unique_runtime_step_ids(self):
        step_ids = [step.id for step in self.runtime_data_flow]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("runtime data flow step ids must be unique")
        return self


class DeepReportStageResult(BaseModel):
    status: str
    report_id: int | None = None
    repo_url: str = ""
    message: str = ""
