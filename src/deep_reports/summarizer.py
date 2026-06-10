from pathlib import Path

from .models import RepoInspection, SourcePackage

MAX_KEY_FILE_CONTENT = 2000


def _manifest_names(manifests: dict[str, str]) -> set[str]:
    return {Path(path).name.lower() for path in manifests}


def _detect_tech_stack(manifests: dict[str, str], file_tree: list[str]) -> dict:
    languages = set()
    frameworks = set()
    dependencies = set()
    manifest_names = _manifest_names(manifests)
    joined = "\n".join(manifests.values()).lower()

    if any(path.endswith(".py") for path in file_tree) or "pyproject.toml" in manifest_names:
        languages.add("Python")
    if any(path.endswith((".ts", ".tsx", ".js", ".jsx")) for path in file_tree) or "package.json" in manifest_names:
        languages.add("JavaScript/TypeScript")
    if "go.mod" in manifest_names:
        languages.add("Go")
    if "cargo.toml" in manifest_names:
        languages.add("Rust")

    if "fastapi" in joined:
        frameworks.add("FastAPI")
    if "next" in joined:
        frameworks.add("Next.js")
    if "react" in joined:
        frameworks.add("React")
    if "openai" in joined:
        dependencies.add("OpenAI")
    if "langchain" in joined:
        dependencies.add("LangChain")

    return {
        "languages": sorted(languages),
        "frameworks": sorted(frameworks),
        "dependencies": sorted(dependencies),
    }


def _append_evidence(evidence: list[dict], seen_paths: set[str], path: str, reason: str) -> None:
    if path in seen_paths:
        return
    evidence.append({"path": path, "reason": reason})
    seen_paths.add(path)


def _build_evidence(inspection: RepoInspection) -> list[dict]:
    evidence = []
    seen_paths = set()
    output_key_files = inspection.key_files[:15]

    for path in list(inspection.manifests)[:8]:
        _append_evidence(evidence, seen_paths, path, "manifest 显示技术栈和依赖")

    key_paths = {item.path for item in output_key_files}
    key_slots_needed = len(key_paths - seen_paths)
    entry_limit = min(8, max(0, 30 - len(evidence) - key_slots_needed))
    for path in inspection.entry_files[:entry_limit]:
        _append_evidence(evidence, seen_paths, path, "入口文件")
    for item in output_key_files:
        _append_evidence(evidence, seen_paths, item.path, item.reason)

    if len(evidence) >= 30:
        return evidence[:30]

    for path in list(inspection.manifests)[8:]:
        _append_evidence(evidence, seen_paths, path, "manifest 显示技术栈和依赖")
        if len(evidence) >= 30:
            return evidence
    for path in inspection.entry_files[entry_limit:]:
        _append_evidence(evidence, seen_paths, path, "入口文件")
        if len(evidence) >= 30:
            return evidence
    for item in inspection.key_files[15:]:
        _append_evidence(evidence, seen_paths, item.path, item.reason)
        if len(evidence) >= 30:
            return evidence

    return evidence


def build_source_package(inspection: RepoInspection) -> SourcePackage:
    key_files = [
        item.model_copy(update={"content": item.content[:MAX_KEY_FILE_CONTENT]})
        for item in inspection.key_files[:15]
    ]
    return SourcePackage(
        repo_url=inspection.repo_url,
        repo_name=inspection.repo_name,
        commit_sha=inspection.commit_sha,
        readme_excerpt=inspection.readme[:4000],
        tech_stack=_detect_tech_stack(inspection.manifests, inspection.file_tree),
        file_tree_summary="\n".join(inspection.file_tree[:300]),
        entry_files=inspection.entry_files,
        key_files=key_files,
        evidence=_build_evidence(inspection),
    )
