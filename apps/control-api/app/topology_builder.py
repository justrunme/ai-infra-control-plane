"""Platform and fleet topology graph builders."""

from datetime import UTC, datetime

from app.fleet_service import build_fleet_clusters
from app.inventory import get_capacity_status, get_cost_status
from app.topology import (
    TopologyEdge,
    TopologyNode,
    TopologySignal,
    TopologyStatus,
)


def get_platform_topology() -> TopologyStatus:
    # Resolve probes via app.main so tests can monkeypatch fetch_*.
    from app import main as app_main

    models = app_main.get_model_inventory()
    capacity_status = get_capacity_status(models)
    cost_status = get_cost_status(models)

    _, ollama_latency_ms, ollama_error = app_main.fetch_ollama_tags()
    ollama_health = "healthy" if ollama_error is None else "degraded"
    _, vllm_latency_ms, vllm_error = app_main.fetch_vllm_models()
    vllm_health = "healthy" if vllm_error is None else "degraded"

    return TopologyStatus(
        updated_at=datetime.now(UTC).isoformat(),
        graph_version="v1",
        nodes=[
            TopologyNode(
                id="k3s",
                label="k3s cluster",
                kind="cluster",
                health="unknown",
                signals=[
                    TopologySignal(
                        name="node_count",
                        value=1,
                        unit="nodes",
                        description=(
                            "Bootstrap target from the Terraform k3s example."
                        ),
                    )
                ],
            ),
            TopologyNode(
                id="control-api",
                label="Control API",
                kind="api",
                health=(
                    "healthy" if capacity_status.healthy_models else "degraded"
                ),
                signals=[
                    TopologySignal(
                        name="models",
                        value=capacity_status.models,
                        unit="count",
                        description="Models known by the control plane.",
                    ),
                    TopologySignal(
                        name="capacity",
                        value=capacity_status.total_capacity_tokens_per_second,
                        unit="tokens_per_second",
                        description="Aggregate serving capacity.",
                    ),
                    TopologySignal(
                        name="estimated_cost",
                        value=cost_status.estimated_hourly_cost,
                        unit="USD_per_hour",
                        description="Estimated hourly model serving cost.",
                    ),
                ],
            ),
            TopologyNode(
                id="ollama",
                label="Ollama",
                kind="inference-backend",
                health=ollama_health,
                signals=[
                    TopologySignal(
                        name="probe_endpoint",
                        value="/api/tags",
                        unit="http_path",
                        description="Endpoint used by the Ollama backend probe.",
                    ),
                    TopologySignal(
                        name="latency",
                        value=ollama_latency_ms,
                        unit="ms",
                        description="Live latency from the Ollama backend probe.",
                    ),
                ],
            ),
            TopologyNode(
                id="vllm",
                label="vLLM",
                kind="inference-backend",
                health=vllm_health,
                signals=[
                    TopologySignal(
                        name="probe_endpoint",
                        value="/v1/models",
                        unit="http_path",
                        description=(
                            "OpenAI-compatible endpoint used by the vLLM probe."
                        ),
                    ),
                    TopologySignal(
                        name="latency",
                        value=vllm_latency_ms,
                        unit="ms",
                        description="Live latency from the vLLM backend probe.",
                    ),
                ],
            ),
            TopologyNode(
                id="openwebui",
                label="OpenWebUI",
                kind="ui",
                health="unknown",
                signals=[
                    TopologySignal(
                        name="role",
                        value="operator-ui",
                        unit="component",
                        description="Planned private AI user interface.",
                    )
                ],
            ),
            TopologyNode(
                id="prometheus",
                label="Prometheus",
                kind="observability",
                health="healthy",
                signals=[
                    TopologySignal(
                        name="scrape_target",
                        value="/metrics",
                        unit="http_path",
                        description="Control API metrics endpoint.",
                    )
                ],
            ),
            TopologyNode(
                id="grafana",
                label="Grafana",
                kind="observability",
                health="healthy",
                signals=[
                    TopologySignal(
                        name="dashboards",
                        value=3,
                        unit="count",
                        description=(
                            "Control plane, logs, and topology dashboards."
                        ),
                    )
                ],
            ),
            TopologyNode(
                id="loki",
                label="Loki",
                kind="observability",
                health="unknown",
                signals=[
                    TopologySignal(
                        name="retention",
                        value=168,
                        unit="hours",
                        description="Example Loki retention window.",
                    )
                ],
            ),
            TopologyNode(
                id="argocd",
                label="Argo CD",
                kind="gitops",
                health="unknown",
                signals=[
                    TopologySignal(
                        name="sync_target",
                        value="helm-chart",
                        unit="component",
                        description="GitOps deployment target.",
                    )
                ],
            ),
            TopologyNode(
                id="helm-chart",
                label="AI Control Plane Helm chart",
                kind="package",
                health="healthy",
                signals=[
                    TopologySignal(
                        name="autoscaling",
                        value="enabled",
                        unit="feature",
                        description="Horizontal Pod Autoscaler support.",
                    )
                ],
            ),
            TopologyNode(
                id="forecasting",
                label="Forecasting layer",
                kind="forecasting",
                health="healthy",
                signals=[
                    TopologySignal(
                        name="predicted_saturation",
                        value=15,
                        unit="minutes",
                        description=(
                            "Example lead time from autoscaling simulator."
                        ),
                    )
                ],
            ),
            TopologyNode(
                id="opa",
                label="OPA policy gates",
                kind="security",
                health="healthy",
                signals=[
                    TopologySignal(
                        name="policy_gate",
                        value="enabled",
                        unit="feature",
                        description="Rendered Kubernetes manifest checks.",
                    )
                ],
            ),
        ],
        edges=[
            TopologyEdge(
                source="control-api", target="ollama", relationship="probes"
            ),
            TopologyEdge(
                source="control-api", target="vllm", relationship="probes"
            ),
            TopologyEdge(
                source="openwebui", target="control-api", relationship="serves"
            ),
            TopologyEdge(
                source="prometheus",
                target="control-api",
                relationship="scrapes",
            ),
            TopologyEdge(
                source="grafana",
                target="prometheus",
                relationship="visualizes",
            ),
            TopologyEdge(
                source="grafana", target="loki", relationship="visualizes"
            ),
            TopologyEdge(
                source="loki", target="control-api", relationship="collects"
            ),
            TopologyEdge(
                source="argocd", target="helm-chart", relationship="deploys"
            ),
            TopologyEdge(
                source="helm-chart",
                target="control-api",
                relationship="packages",
            ),
            TopologyEdge(
                source="control-api", target="k3s", relationship="runs-on"
            ),
            TopologyEdge(
                source="forecasting",
                target="control-api",
                relationship="forecasts",
            ),
            TopologyEdge(
                source="opa", target="helm-chart", relationship="enforces"
            ),
        ],
    )


def get_fleet_topology() -> TopologyStatus:
    from app import main as app_main

    fleet = build_fleet_clusters()
    capacity_status = get_capacity_status(app_main.get_model_inventory())
    cost_status = get_cost_status(app_main.get_model_inventory())

    nodes: list[TopologyNode] = [
        TopologyNode(
            id="control-api",
            label="Control Plane",
            kind="api",
            health=(
                "healthy" if capacity_status.healthy_models else "degraded"
            ),
            signals=[
                TopologySignal(
                    name="fleet_clusters",
                    value=fleet.summary.cluster_count,
                    unit="count",
                    description=(
                        "Clusters registered in the fleet registry."
                    ),
                ),
                TopologySignal(
                    name="healthy_clusters",
                    value=fleet.summary.healthy_clusters,
                    unit="count",
                    description="Clusters with healthy inference backends.",
                ),
                TopologySignal(
                    name="capacity",
                    value=capacity_status.total_capacity_tokens_per_second,
                    unit="tokens_per_second",
                    description=(
                        "Aggregate serving capacity on the primary cluster."
                    ),
                ),
                TopologySignal(
                    name="estimated_cost",
                    value=cost_status.estimated_hourly_cost,
                    unit="USD_per_hour",
                    description="Estimated hourly model serving cost.",
                ),
            ],
        )
    ]
    edges: list[TopologyEdge] = []

    for cluster in fleet.clusters:
        node_id = f"cluster-{cluster.id}"
        nodes.append(
            TopologyNode(
                id=node_id,
                label=cluster.label,
                kind="cluster",
                health=cluster.health,
                signals=[
                    TopologySignal(
                        name="cloud",
                        value=cluster.cloud,
                        unit="provider",
                        description="Cloud or site label for placement policy.",
                    ),
                    TopologySignal(
                        name="region",
                        value=cluster.region,
                        unit="region",
                        description="Geographic or logical region.",
                    ),
                    TopologySignal(
                        name="environment",
                        value=cluster.environment,
                        unit="environment",
                        description="Mapped policy pack environment.",
                    ),
                    TopologySignal(
                        name="node_count",
                        value=cluster.node_count,
                        unit="nodes",
                        description="Worker nodes in the cluster.",
                    ),
                    TopologySignal(
                        name="healthy_models",
                        value=cluster.healthy_models,
                        unit="count",
                        description="Healthy models reported for the cluster.",
                    ),
                ],
            )
        )
        edges.append(
            TopologyEdge(
                source="control-api",
                target=node_id,
                relationship="runs-on" if cluster.primary else "probes",
            )
        )

    return TopologyStatus(
        updated_at=fleet.summary.updated_at,
        graph_version="v2-fleet",
        nodes=nodes,
        edges=edges,
    )
