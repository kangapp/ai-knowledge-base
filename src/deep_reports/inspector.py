import subprocess
import tempfile
from pathlib import Path

from .models import RepoFile, RepoInspection

MAX_FILE_SIZE = 80_000
MAX_KEY_FILES = 15
MAX_TREE_FILES = 300

SKIP_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "vendor",
    "__pycache__",
}
MANIFEST_NAMES = {
    "cargo.toml",
    "dockerfile",
    "docker-compose.yml",
    "go.mod",
    "package-lock.json",
    "package.json",
    "poetry.lock",
    "pyproject.toml",
    "requirements.txt",
    "setup.cfg",
    "setup.py",
    "uv.lock",
}
ENTRY_NAMES = {
    "app.py",
    "cli.py",
    "index.js",
    "index.ts",
    "main.go",
    "main.js",
    "main.py",
    "main.ts",
    "server.js",
    "server.py",
    "server.ts",
}
KEY_PATH_PARTS = {
    "agent",
    "analyzer",
    "api",
    "app",
    "client",
    "core",
    "cli",
    "db",
    "graph",
    "index",
    "main",
    "model",
    "models",
    "packages",
    "pipeline",
    "schema",
    "server",
    "service",
    "store",
    "src",
    "workflow",
}
KEY_SUFFIXES = {".go", ".js", ".jsx", ".py", ".ts", ".tsx"}


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _should_skip(path: Path, root: Path) -> bool:
    if path.is_symlink():
        return True
    relative_parts = path.relative_to(root).parts
    return any(part in SKIP_DIRS for part in relative_parts)


def _is_text_file(path: Path) -> bool:
    try:
        with path.open("rb") as file:
            chunk = file.read(4096)
    except OSError:
        return False
    if b"\x00" in chunk:
        return False
    try:
        chunk.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _read_limited(path: Path, limit: int = MAX_FILE_SIZE) -> str:
    if path.stat().st_size > limit:
        return ""
    if not _is_text_file(path):
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _is_manifest(relative_path: str) -> bool:
    name = Path(relative_path).name.lower()
    return name in MANIFEST_NAMES


def _is_entry(relative_path: str) -> bool:
    return Path(relative_path).name.lower() in ENTRY_NAMES


def _is_key_file(relative_path: str, path: Path) -> bool:
    if path.suffix.lower() not in KEY_SUFFIXES:
        return False
    lower_parts = [part.lower() for part in Path(relative_path).parts]
    stem = path.stem.lower()
    return stem in KEY_PATH_PARTS or any(part in KEY_PATH_PARTS for part in lower_parts)


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if _should_skip(path, root):
            continue
        if path.is_file() and path.stat().st_size <= MAX_FILE_SIZE and _is_text_file(path):
            files.append(path)
    return files


def _read_commit_sha(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return ""
    return result.stdout.strip()


def inspect_local_repo(root: Path, *, repo_url: str, repo_name: str) -> RepoInspection:
    root = root.resolve()
    result = RepoInspection(
        repo_url=repo_url,
        repo_name=repo_name,
        commit_sha=_read_commit_sha(root),
    )
    files = _iter_files(root)

    for path in files[:MAX_TREE_FILES]:
        result.file_tree.append(_relative_path(path, root))

    for path in files:
        relative_path = _relative_path(path, root)
        lower_name = path.name.lower()
        if lower_name.startswith("readme") and not result.readme:
            result.readme = _read_limited(path)
        if _is_manifest(relative_path):
            content = _read_limited(path)
            if content:
                result.manifests[relative_path] = content
        if _is_entry(relative_path):
            result.entry_files.append(relative_path)

        if len(result.key_files) >= MAX_KEY_FILES:
            continue
        if _is_key_file(relative_path, path):
            result.key_files.append(
                RepoFile(
                    path=relative_path,
                    size=path.stat().st_size,
                    content=_read_limited(path),
                    reason="matched key source path",
                )
            )

    if len(files) > MAX_TREE_FILES:
        result.skipped_reason = f"file_tree truncated to {MAX_TREE_FILES} files"
    return result


def clone_and_inspect(repo_url: str, repo_name: str, timeout_seconds: int = 60) -> RepoInspection:
    with tempfile.TemporaryDirectory(prefix="repo-inspector-") as temp_dir:
        clone_dir = Path(temp_dir) / "repo"
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(clone_dir)],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return inspect_local_repo(clone_dir, repo_url=repo_url, repo_name=repo_name)
