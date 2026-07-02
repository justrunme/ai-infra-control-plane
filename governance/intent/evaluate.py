#!/usr/bin/env python3
"""Resolve natural-language intents into governed orchestration plans."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def parse_scalar(value: str) -> Any:
    normalized = value.strip()
    if normalized == "":
        return ""
    if normalized.lower() in {"true", "yes"}:
        return True
    if normalized.lower() in {"false", "no"}:
        return False
    try:
        if "." in normalized:
            return float(normalized)
        return int(normalized)
    except ValueError:
        return normalized


def parse_routes(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"intent routes file does not exist: {path}")

    config: dict[str, Any] = {"default_intent": "general_assistant", "intents": {}}
    section: str | None = None
    current_intent: str | None = None
    current_list_key: str | None = None

    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0:
            key, _, value = line.partition(":")
            if key == "default_intent":
                config["default_intent"] = value.strip()
                section = None
                continue
            if key == "intents":
                section = "intents"
                continue
            raise ValueError(f"unsupported intent routes line: {raw_line}")

        if section == "intents":
            if indent == 2 and line.endswith(":"):
                current_intent = line[:-1]
                current_list_key = None
                config["intents"][current_intent] = {}
                continue
            if indent == 4 and current_intent is not None:
                if line.startswith("- "):
                    if current_list_key:
                        config["intents"][current_intent].setdefault(
                            current_list_key, []
                        ).append(line[2:])
                    continue
                key, _, value = line.partition(":")
                if not key:
                    raise ValueError(f"unsupported intent entry: {raw_line}")
                if not value.strip():
                    if key == "keywords":
                        config["intents"][current_intent][key] = []
                        current_list_key = key
                        continue
                    raise ValueError(f"unsupported intent entry: {raw_line}")
                current_list_key = None
                config["intents"][current_intent][key] = parse_scalar(value)
                continue
            if indent == 6 and current_intent is not None and line.startswith("- "):
                if current_list_key:
                    config["intents"][current_intent].setdefault(
                        current_list_key, []
                    ).append(line[2:])
                    continue

        raise ValueError(f"unsupported intent routes line: {raw_line}")

    return config


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{3,}", text.lower())}


def score_intent(message: str, intent_name: str, intent: dict[str, Any]) -> float:
    if intent.get("default"):
        return 0.01

    keywords = intent.get("keywords", [])
    if not isinstance(keywords, list) or not keywords:
        return 0.0

    tokens = _tokenize(message)
    if not tokens:
        return 0.0

    hits = sum(1 for keyword in keywords if str(keyword).lower() in tokens)
    if hits == 0:
        return 0.0
    return hits / len(keywords)


def resolve_intent(
    message: str, routes: dict[str, Any]
) -> tuple[str, dict[str, Any], float]:
    intents = routes.get("intents", {})
    best_name = str(routes.get("default_intent", "general_assistant"))
    best_intent = intents.get(best_name, {})
    best_score = 0.0

    for name, intent in intents.items():
        score = score_intent(message, name, intent)
        if score > best_score:
            best_score = score
            best_name = name
            best_intent = intent

    if best_score == 0.0:
        for name, intent in intents.items():
            if intent.get("default"):
                best_name = name
                best_intent = intent
                best_score = 0.01
                break

    confidence = round(min(1.0, max(best_score, 0.01)), 3)
    return best_name, best_intent, confidence


def select_cluster(
    *,
    preferred_region: str,
    environment: str,
    clusters: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any] | None]:
    candidates = [
        (name, entry)
        for name, entry in clusters.items()
        if str(entry.get("region", "")) == preferred_region
    ]
    if environment:
        env_matches = [
            item
            for item in candidates
            if str(item[1].get("environment", "")) == environment
        ]
        if env_matches:
            candidates = env_matches

    if not candidates:
        return "", None

    primary = next((item for item in candidates if item[1].get("primary")), None)
    if primary:
        return primary[0], primary[1]

    name, entry = sorted(candidates, key=lambda item: item[0])[0]
    return name, entry


def build_orchestration_plan(
    request: dict[str, Any],
    *,
    routes: dict[str, Any],
    agents: dict[str, dict[str, Any]],
    models: dict[str, dict[str, Any]],
    clusters: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    message = str(request.get("message", "")).strip()
    intent_name, intent, confidence = resolve_intent(message, routes)

    agent_name = str(intent.get("agent", "")).strip()
    agent_entry = agents.get(agent_name, {})
    if agent_entry.get("forbidden"):
        return {
            "intent": intent_name,
            "confidence": confidence,
            "forbidden": True,
            "reasons": [f"agent {agent_name} is forbidden"],
            "plan": {},
        }

    model = str(request.get("model") or agent_entry.get("model") or "llama3.1:8b")
    model_entry = models.get(model, {})
    region = str(
        request.get("region")
        or intent.get("preferred_region")
        or request.get("preferred_region")
        or "local"
    )
    environment = str(request.get("environment") or "development")
    cluster_name, cluster = select_cluster(
        preferred_region=region,
        environment=environment,
        clusters=clusters,
    )

    tools = list(agent_entry.get("tools", []))
    provider = str(request.get("provider") or intent.get("preferred_runtime") or "ollama")
    if bool(model_entry.get("external_provider")):
        provider = "openai"

    plan = {
        "agent": agent_name,
        "model": model,
        "tools": tools,
        "region": region,
        "runtime": provider,
        "cluster": cluster_name or None,
        "policy_pack": str(
            request.get("policy_pack") or agent_entry.get("policy_pack") or ""
        ),
        "namespace": str(request.get("namespace") or "ai-dev"),
        "team": str(request.get("team") or "platform"),
    }

    reasons: list[str] = []
    forbidden = False
    if not agent_entry:
        forbidden = True
        reasons.append(f"agent {agent_name} is not registered")
    if model_entry.get("forbidden"):
        forbidden = True
        reasons.append(f"model {model} is forbidden")

    allowed_teams = agent_entry.get("allowed_teams")
    team = plan["team"]
    if isinstance(allowed_teams, list) and allowed_teams and team not in allowed_teams:
        forbidden = True
        reasons.append(f"team {team} is not allowed to use agent {agent_name}")

    return {
        "intent": intent_name,
        "description": intent.get("description"),
        "confidence": confidence,
        "forbidden": forbidden,
        "reasons": reasons,
        "plan": plan,
        "cluster": {
            "name": cluster_name,
            "region": cluster.get("region") if cluster else region,
            "cloud": cluster.get("cloud") if cluster else None,
            "environment": cluster.get("environment") if cluster else environment,
        },
    }
