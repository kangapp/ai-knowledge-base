from pathlib import Path


ROOT = Path(__file__).parent.parent


def test_deploy_waits_for_pipeline_health_then_builds_static_site():
    workflow = (ROOT / ".github/workflows/deploy.yml").read_text()

    compose_up = workflow.index("docker compose up -d")
    health_check = workflow.index(
        "docker compose exec -T pipeline curl -fsS http://localhost:8000/api/health"
    )
    static_build = workflow.index(
        "docker compose exec -T pipeline curl -fsS -X POST "
        "http://localhost:8000/api/pipeline/build"
    )

    assert compose_up < health_check < static_build
    assert "for attempt in $(seq 1 30)" in workflow
    assert 'if [ "$attempt" -eq 30 ]' in workflow
    assert "docker compose logs --tail=100 pipeline" in workflow
    assert "test -f output/deep.html" in workflow
    assert "test -f output/deep-report.html" in workflow
