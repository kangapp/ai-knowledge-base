import subprocess
from pathlib import Path

from src.deep_reports.inspector import clone_and_inspect, inspect_local_repo
from src.deep_reports.models import RepoFile, RepoInspection
from src.deep_reports.summarizer import build_source_package


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


def test_build_source_package_extracts_stack_and_evidence():
    inspection = RepoInspection(
        repo_url="https://github.com/org/tool",
        repo_name="org/tool",
        readme="# Tool\nAI repo analyzer",
        manifests={"pyproject.toml": "[project]\ndependencies=['fastapi','openai']"},
        file_tree=["pyproject.toml", "src/main.py", "src/models.py"],
        entry_files=["src/main.py"],
        key_files=[
            RepoFile(path="src/main.py", size=20, content="from fastapi import FastAPI", reason="入口文件"),
            RepoFile(path="src/models.py", size=20, content="class Document: pass", reason="核心目录源码"),
        ],
    )

    package = build_source_package(inspection)

    assert package.repo_name == "org/tool"
    assert "Python" in package.tech_stack["languages"]
    assert "FastAPI" in package.tech_stack["frameworks"]
    assert package.entry_files == ["src/main.py"]
    assert package.evidence[0]["path"] == "pyproject.toml"


def test_build_source_package_detects_nested_manifests_and_limits_content():
    inspection = RepoInspection(
        repo_url="https://github.com/org/app",
        repo_name="org/app",
        readme="R" * 4001,
        manifests={
            "frontend/package.json": '{"dependencies":{"next":"latest","react":"latest"}}',
            "services/api/go.mod": "module example.com/app",
            "crates/core/Cargo.toml": "[package]\nname = 'core'",
        },
        file_tree=[f"src/file_{index}.ts" for index in range(350)],
        entry_files=[f"frontend/src/main_{index}.tsx" for index in range(35)],
        key_files=[
            RepoFile(path=f"src/file_{index}.ts", size=20, content="export {}", reason="核心目录源码")
            for index in range(20)
        ],
    )

    package = build_source_package(inspection)

    assert "JavaScript/TypeScript" in package.tech_stack["languages"]
    assert "Go" in package.tech_stack["languages"]
    assert "Rust" in package.tech_stack["languages"]
    assert "Next.js" in package.tech_stack["frameworks"]
    assert "React" in package.tech_stack["frameworks"]
    assert len(package.readme_excerpt) == 4000
    assert len(package.file_tree_summary.splitlines()) == 300
    assert len(package.key_files) == 15
    assert len(package.evidence) == 30
    assert any(item["path"] == "src/file_0.ts" for item in package.evidence)


def test_build_source_package_deduplicates_evidence_paths():
    inspection = RepoInspection(
        repo_url="https://github.com/org/tool",
        repo_name="org/tool",
        entry_files=["src/main.py"],
        key_files=[
            RepoFile(path="src/main.py", size=20, content="print('ok')", reason="入口文件"),
        ],
    )

    package = build_source_package(inspection)

    paths = [item["path"] for item in package.evidence]
    assert paths.count("src/main.py") == 1


def test_build_source_package_evidence_covers_all_output_key_files():
    inspection = RepoInspection(
        repo_url="https://github.com/org/tool",
        repo_name="org/tool",
        manifests={f"manifest_{index}.toml": "dependency" for index in range(8)},
        entry_files=[f"src/entry_{index}.py" for index in range(8)],
        key_files=[
            RepoFile(path=f"src/file_{index}.py", size=20, content="print('ok')", reason="核心目录源码")
            for index in range(15)
        ],
    )

    package = build_source_package(inspection)

    key_paths = {item.path for item in package.key_files}
    evidence_paths = {item["path"] for item in package.evidence}
    assert len(package.evidence) <= 30
    assert key_paths <= evidence_paths
