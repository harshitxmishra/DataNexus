import json
import yaml
from pathlib import Path

def validate():
    yaml_files = [
        "docker-compose.monitoring.yml",
        "monitoring/otel/otel-collector-config.yaml",
        "monitoring/prometheus/prometheus.yml",
        "monitoring/grafana/provisioning/datasources/prometheus.yml",
        "monitoring/grafana/provisioning/dashboards/dashboards.yml",
    ]

    json_files = [
        "monitoring/grafana/dashboards/datanexus-sre-overview.json",
    ]

    for yf in yaml_files:
        path = Path(yf)
        assert path.exists(), f"File missing: {yf}"
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            assert isinstance(data, dict), f"YAML root is not dict in {yf}"
        print(f"[OK] YAML valid: {yf}")

    for jf in json_files:
        path = Path(jf)
        assert path.exists(), f"File missing: {jf}"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert isinstance(data, dict), f"JSON root is not dict in {jf}"
            assert "panels" in data, f"panels missing in {jf}"
            assert len(data["panels"]) >= 5, f"Expected at least 5 panels in {jf}"
        print(f"[OK] JSON valid: {jf} ({len(data['panels'])} panels)")

    print("[SUCCESS] All monitoring configuration files are syntactically and semantically valid.")

if __name__ == "__main__":
    validate()
