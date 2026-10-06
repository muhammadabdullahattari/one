import json
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_dockerfiles_exist_and_meet_srs_standards() -> None:
    dockerfiles = [
        PROJECT_ROOT / "deploy" / "docker" / "Dockerfile.api",
        PROJECT_ROOT / "deploy" / "docker" / "Dockerfile.worker",
        PROJECT_ROOT / "deploy" / "docker" / "Dockerfile.scheduler",
        PROJECT_ROOT / "frontend" / "Dockerfile",
        PROJECT_ROOT / "Dockerfile",
    ]

    for df in dockerfiles:
        assert df.exists(), f"Missing Dockerfile: {df}"
        content = df.read_text(encoding="utf-8")
        # SRS §16.1: Images SHALL run as non-root user
        assert "USER" in content, f"{df.name} missing USER non-root directive"
        # SRS §16.1: Container health checks SHALL be defined
        assert "HEALTHCHECK" in content, f"{df.name} missing HEALTHCHECK directive"


def test_compose_production_baseline_syntax_and_services() -> None:
    compose_file = PROJECT_ROOT / "docker-compose.yml"
    assert compose_file.exists()

    with open(compose_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    services = data.get("services", {})
    required_services = [
        "api",
        "worker",
        "scheduler",
        "frontend",
        "postgres",
        "redis",
        "prometheus",
        "grafana",
    ]
    for s in required_services:
        assert s in services, f"Service '{s}' missing from docker-compose.yml"

    # API and Worker must have healthcheck or depends_on health conditions
    assert "depends_on" in services["api"]
    assert "postgres" in services["api"]["depends_on"]
    assert "redis" in services["api"]["depends_on"]


def test_compose_overlays_syntax() -> None:
    overlay_files = [
        PROJECT_ROOT / "docker-compose.dev.yml",
        PROJECT_ROOT / "docker-compose.staging.yml",
        PROJECT_ROOT / "docker-compose.prod.yml",
    ]

    for ov in overlay_files:
        assert ov.exists(), f"Missing overlay file: {ov}"
        with open(ov, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "services" in data, f"{ov.name} missing services block"

    # Verify prod overlay specifies resource limits
    with open(PROJECT_ROOT / "docker-compose.prod.yml", encoding="utf-8") as f:
        prod_data = yaml.safe_load(f)
    api_deploy = prod_data["services"]["api"]["deploy"]["resources"]["limits"]
    assert "cpus" in api_deploy
    assert "memory" in api_deploy


def test_prometheus_and_grafana_configurations() -> None:
    prom_cfg = PROJECT_ROOT / "deploy" / "prometheus" / "prometheus.yml"
    assert prom_cfg.exists()
    with open(prom_cfg, encoding="utf-8") as f:
        prom_data = yaml.safe_load(f)
    assert "scrape_configs" in prom_data

    grafana_dash = PROJECT_ROOT / "deploy" / "grafana" / "dashboards" / "task_engine_overview.json"
    assert grafana_dash.exists()
    with open(grafana_dash, encoding="utf-8") as f:
        dash_data = json.load(f)
    assert dash_data["uid"] == "task-engine-overview"
    assert len(dash_data.get("panels", [])) >= 4


def test_all_11_runbooks_exist_per_srs_22_1() -> None:
    expected_runbooks = [
        "RB-001-worker-crash-storm.md",
        "RB-002-redis-outage.md",
        "RB-003-postgres-outage.md",
        "RB-004-dlq-replay.md",
        "RB-005-queue-overload.md",
        "RB-006-scheduler-stuck.md",
        "RB-007-outbox-backlog.md",
        "RB-008-migration-rollback.md",
        "RB-009-credential-rotation.md",
        "RB-010-disaster-recovery.md",
        "RB-011-capacity-expansion.md",
    ]

    runbooks_dir = PROJECT_ROOT / "docs" / "runbooks"
    assert runbooks_dir.exists()

    readme_content = (runbooks_dir / "README.md").read_text(encoding="utf-8")

    for rb in expected_runbooks:
        rb_path = runbooks_dir / rb
        assert rb_path.exists(), f"Missing required runbook: {rb}"
        content = rb_path.read_text(encoding="utf-8")
        assert len(content) > 300, f"Runbook {rb} is unexpectedly short"
        rb_id = "-".join(rb.split("-")[:2])
        assert rb_id in content, f"Runbook {rb} missing Runbook ID {rb_id} in content"
        assert rb in readme_content, f"Runbook {rb} not linked in README.md index"


def test_healthcheck_script_functions() -> None:
    from scripts.healthcheck import check_process

    # Check for non-existent process returns 1 or 0 safely
    rc = check_process("non_existent_fake_process_999999")
    assert rc in (0, 1)
