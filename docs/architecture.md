# Architecture

AI Infrastructure Control Plane is a Kubernetes-native platform shell around private AI inference workloads.

It is not an agent runtime or an agent orchestration framework. The system does not try to replace LangGraph, CrewAI, OpenAI Agents SDK, or other workflow engines. Its job is to operate the infrastructure those services may depend on: model serving, health, latency, capacity, cost, deployment, observability, and security.

## Reference Architecture

```mermaid
flowchart TB
    User["AI Consumer"]
    API["Control API<br/>FastAPI"]

    subgraph ControlPlane["AI Infrastructure Control Plane"]
        Capacity["Capacity Planner"]
        Cost["Cost Governance"]
        Risk["Risk Scoring"]
        Approval["Approval Engine"]
        Twin["Digital Twin"]
    end

    subgraph AI["AI Workloads"]
        Ollama["Ollama"]
        VLLM["vLLM"]
        Models["Foundation Models"]
    end

    subgraph Observability["Observability"]
        OTel["OpenTelemetry"]
        Prom["Prometheus"]
        Graf["Grafana"]
        Loki["Loki"]
    end

    User --> API
    API --> Capacity
    API --> Cost
    API --> Risk
    API --> Approval
    API --> Twin
    Capacity --> Ollama
    Capacity --> VLLM
    Ollama --> Models
    VLLM --> Models
    Ollama --> OTel
    VLLM --> OTel
    OTel --> Prom
    OTel --> Loki
    Prom --> Graf
    Loki --> Graf
    Twin --> Graf
```

## Components

- **Control API**: exposes health, model status, capacity, and cost signals.
- **Inference backends**: adapters for Ollama, future vLLM, OpenWebUI, and managed endpoints.
- **Kubernetes package**: Helm chart for deploying the API and later backend workers.
- **Infrastructure modules**: Terraform modules for bootstrap compute and cluster prerequisites.
- **Observability**: Prometheus metrics, Grafana dashboards, Loki logs, and OpenTelemetry GenAI telemetry prototype.
- **Planning**: TimesFM forecasting and forecast-driven autoscaling recommendations.
- **Security**: Trivy scans and OPA policy checks for rendered Kubernetes manifests.
- **Governance**: cost decisions, risk scoring, approval workflow, and end-to-end governance pipeline.
- **GitOps**: Argo CD manifests and Helm packaging for repeatable deployment.
