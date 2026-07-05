from pathlib import Path


ROOT = Path(__file__).parent.parent


def test_deploy_waits_for_pipeline_health_then_builds_static_site():
    workflow = (ROOT / ".github/workflows/deploy.yml").read_text()

    compose_up = workflow.index(
        "docker compose up -d --wait --wait-timeout 90"
    )
    health_check = workflow.index(
        "docker compose exec -T pipeline curl -fsS http://localhost:8000/api/health"
    )
    static_build = workflow.index(
        "docker compose exec -T pipeline curl -fsS -X POST "
        "http://localhost:8000/api/pipeline/build"
    )

    assert compose_up < health_check < static_build
    assert "docker compose logs --tail=100 pipeline" in workflow
    assert "test -f output/deep.html" in workflow
    assert "test -f output/deep-report.html" in workflow
    assert "test -f output/analysis.html" in workflow
    assert 'if [ -n "$PUBLIC_BASE_URL" ]; then' in workflow
    assert 'curl -fsS "${PUBLIC_BASE_URL%/}/api/health"' in workflow


def test_deploy_fails_fast_and_retries_image_pull_twice():
    workflow = (ROOT / ".github/workflows/deploy.yml").read_text()

    assert "timeout: 30s" in workflow
    assert "command_timeout: 10m" in workflow
    assert "for pull_attempt in 1 2" in workflow
    assert "timeout 3m docker compose pull pipeline" in workflow
    assert 'if [ "$pull_attempt" -eq 2 ]' in workflow


def test_deploy_uses_commit_image_and_rolls_back_on_failure():
    workflow = (ROOT / ".github/workflows/deploy.yml").read_text()
    compose = (ROOT / "docker-compose.yml").read_text()

    assert "image_sha:" in workflow
    assert (
        "ghcr.io/${{ github.repository_owner }}/ai-knowledge-base:"
        "${{ needs.resolve.outputs.image_sha }}"
    ) in workflow
    assert "PIPELINE_IMAGE:latest" not in compose
    assert "${PIPELINE_IMAGE:-ghcr.io/kangapp/ai-knowledge-base:latest}" in compose
    assert "trap rollback ERR" in workflow
    assert 'docker image tag "$previous_image_id" "$rollback_image"' in workflow
    assert 'export PIPELINE_IMAGE="$rollback_image"' in workflow
    assert 'docker compose up -d --wait --wait-timeout 90' in workflow
    assert 'output_backup=".deploy-output-backup-${ROLLBACK_SUFFIX}"' in workflow
    assert 'mv "$output_backup" output' in workflow
    assert "docker compose pull failed after 2 attempts\"\n                false" in workflow


def test_pipeline_defaults_to_info_logging_in_compose():
    compose = (ROOT / "docker-compose.yml").read_text()

    assert "LOG_LEVEL: ${LOG_LEVEL:-INFO}" in compose


def test_deploy_supports_manual_ref_and_serializes_deployments():
    workflow = (ROOT / ".github/workflows/deploy.yml").read_text()

    assert "workflow_dispatch:" in workflow
    assert "description: Git ref to build and deploy" in workflow
    assert "concurrency:" in workflow
    assert "group: production-deploy" in workflow
    assert "cancel-in-progress: false" in workflow


def test_deploy_pins_resolvable_action_versions():
    workflow = (ROOT / ".github/workflows/deploy.yml").read_text()

    assert "astral-sh/setup-uv@v8.2.0" in workflow
    assert "astral-sh/setup-uv@v8\n" not in workflow


def test_pipeline_image_installs_repo_inspector_runtime_dependencies():
    dockerfile = (ROOT / "Dockerfile").read_text()

    assert "apt-get install -y --no-install-recommends curl git" in dockerfile
    assert "ghcr.io/astral-sh/uv:0.11.22" in dockerfile
    assert dockerfile.index("apt-get install") < dockerfile.index("COPY src/")


def test_pipeline_image_contains_analysis_pages():
    dockerfile = (ROOT / "Dockerfile").read_text()

    assert "COPY docs/analysis/ ./docs/analysis/" in dockerfile
