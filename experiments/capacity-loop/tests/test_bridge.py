import importlib.util
import json
from pathlib import Path

BRIDGE_PATH = Path(__file__).resolve().parents[1] / "bridge.py"
SAMPLE_FORECAST = (
    Path(__file__).resolve().parents[2]
    / "inference-autoscaling/results/example_forecast.json"
)


def load_bridge():
    spec = importlib.util.spec_from_file_location("capacity_bridge", BRIDGE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_keda_hint_scale_up_from_sample_forecast() -> None:
    bridge = load_bridge()
    forecast = json.loads(SAMPLE_FORECAST.read_text())
    hint = bridge.build_keda_hint(
        forecast,
        target_deployment="vllm-runtime",
        prometheus_metric="vllm:num_requests_waiting",
        threshold_per_replica=4.0,
    )
    assert hint["target_deployment"] == "vllm-runtime"
    assert hint["recommended_replicas"] >= hint["current_replicas"]
    assert hint["keda"]["metric"] == "vllm:num_requests_waiting"
    assert hint["action"] in {"hold", "scale_up", "scale_down"}
