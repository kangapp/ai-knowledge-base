import subprocess
from pathlib import Path

from src.deep_reports.inspector import clone_and_inspect, inspect_local_repo


def test_inspect_local_repo_filters_generated_files_and_finds_key_files(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Tool\nUseful AI repo", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='tool'\ndependencies=['fastapi']\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
    (repo / "src" / "models.py").write_text("class Document: pass\n", encoding="utf-8")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")
    (repo / "dist").mkdir()
    (repo / "dist" / "bundle.js").write_text("ignored", encoding="utf-8")

    result = inspect_local_repo(repo, repo_url="https://github.com/org/tool", repo_name="org/tool")

    assert result.readme.startswith("# Tool")
    assert "pyproject.toml" in result.manifests
    assert "src/main.py" in result.entry_files
    assert "src/models.py" in [item.path for item in result.key_files]
    assert all("node_modules" not in item.path for item in result.key_files)
    assert all("dist" not in path for path in result.file_tree)


def test_inspect_local_repo_skips_binary_and_large_files_from_key_files(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Tool\nUseful AI repo", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (repo / "src" / "binary.py").write_bytes(b"\x00\x01\x02")
    (repo / "src" / "large.py").write_text("x" * 80_001, encoding="utf-8")

    result = inspect_local_repo(repo, repo_url="https://github.com/org/tool", repo_name="org/tool")

    key_paths = [item.path for item in result.key_files]
    assert "src/main.py" in key_paths
    assert "src/binary.py" not in key_paths
    assert "src/large.py" not in key_paths
    assert "src/binary.py" not in result.file_tree
    assert "src/large.py" not in result.file_tree


def test_inspect_local_repo_finds_planned_manifest_entry_and_key_paths(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Tool\nUseful AI repo", encoding="utf-8")
    (repo / "Cargo.toml").write_text("[package]\nname = 'tool'\n", encoding="utf-8")
    (repo / "docker-compose.yml").write_text("services:\n  app:\n    image: tool\n", encoding="utf-8")
    (repo / "packages").mkdir()
    (repo / "packages" / "index.ts").write_text("export const app = true;\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "server.ts").write_text("export function serve() {}\n", encoding="utf-8")
    for directory in ["models", "schema", "db", "store"]:
        path = repo / directory
        path.mkdir()
        (path / "client.py").write_text("class Client: pass\n", encoding="utf-8")

    result = inspect_local_repo(repo, repo_url="https://github.com/org/tool", repo_name="org/tool")

    assert "Cargo.toml" in result.manifests
    assert "docker-compose.yml" in result.manifests
    assert "packages/index.ts" in result.entry_files
    assert "src/server.ts" in result.entry_files
    key_paths = {item.path for item in result.key_files}
    assert {"models/client.py", "schema/client.py", "db/client.py", "store/client.py"}.issubset(key_paths)


def test_inspect_local_repo_skips_symlinks_without_reading_external_content(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("SECRET_OUTSIDE_CONTENT", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Tool\nUseful AI repo", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "main.py").symlink_to(outside)

    result = inspect_local_repo(repo, repo_url="https://github.com/org/tool", repo_name="org/tool")

    assert "src/main.py" not in result.file_tree
    assert "src/main.py" not in [item.path for item in result.key_files]
    assert all("SECRET_OUTSIDE_CONTENT" not in item.content for item in result.key_files)


def test_clone_and_inspect_clones_local_git_repo_and_reads_commit_sha(tmp_path):
    repo = tmp_path / "source"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "README.md").write_text("# Tool\nUseful AI repo", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='tool'\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True, text=True)

    result = clone_and_inspect(str(repo), repo_name="org/tool")

    assert result.repo_url == str(repo)
    assert result.repo_name == "org/tool"
    assert result.commit_sha
    assert result.readme.startswith("# Tool")
    assert "pyproject.toml" in result.manifests
