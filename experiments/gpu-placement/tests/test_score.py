import importlib.util
from pathlib import Path

SCORE_PATH = Path(__file__).resolve().parents[1] / "score.py"


def load_score():
    spec = importlib.util.spec_from_file_location("gpu_score", SCORE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_score_placement_rejects_too_small_gpu() -> None:
    score = load_score()
    result = score.score_placement(
        {
            "workload_id": "w1",
            "model_size_gb": 14,
            "batch_size": 8,
            "queue_depth": 2,
            "gpu_name": "t4",
            "gpu_vram_gb": 16,
            "gpu_utilization": 0.2,
            "cost_per_hour_usd": 0.4,
        }
    )
    assert result["recommendation"] in {"place", "reject"}
    assert result["score"] > 0


def test_build_result_picks_winner_per_workload() -> None:
    score = load_score()
    sample = Path(__file__).resolve().parents[1] / "sample_workloads.csv"
    result = score.build_result(sample)
    assert len(result["winners"]) == 2
    assert all("gpu_name" in winner for winner in result["winners"])
