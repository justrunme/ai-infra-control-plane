"""Durable agent/tool capability contracts (control-plane registry only).

Runtime MCP execution stays in the AI Runtime Platform. This module freezes
capability snapshots with a content digest so evaluate/governance can pin an
active contract instead of only reading mutable YAML on disk.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from app.agent_registry_service import build_agent_registry
from app.decision_store import (
    CapabilityContractRecord,
    DecisionStore,
    get_decision_store,
)
from app.tool_registry_service import build_tool_registry

CapabilityKind = Literal["agent", "tool"]


def _canonical_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def contract_to_dict(record: CapabilityContractRecord) -> dict[str, Any]:
    return {
        "contract_id": record.contract_id,
        "kind": record.kind,
        "name": record.name,
        "tenant_id": record.tenant_id,
        "status": record.status,
        "version": record.version,
        "content_digest": record.content_digest,
        "capabilities": record.capabilities,
        "source": record.source,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "activated_at": record.activated_at,
    }


def sync_from_filesystem(
    *,
    tenant_id: str = "platform",
    activate: bool = False,
    store: DecisionStore | None = None,
) -> list[CapabilityContractRecord]:
    """Import YAML agent/tool registries into durable capability contracts."""
    decision_store = store or get_decision_store()
    synced: list[CapabilityContractRecord] = []

    agents = build_agent_registry()
    for agent in agents.agents:
        payload = agent.model_dump()
        digest = _canonical_digest(payload)
        record = decision_store.upsert_capability_contract(
            kind="agent",
            name=agent.name,
            tenant_id=tenant_id,
            version=digest[-12:],
            content_digest=digest,
            capabilities=payload,
            source="filesystem",
            status="draft",
        )
        if activate and record.status != "active":
            record = decision_store.set_capability_contract_status(
                record.contract_id, "active"
            )
        synced.append(record)

    tools = build_tool_registry()
    for tool in tools.tools:
        payload = tool.model_dump()
        digest = _canonical_digest(payload)
        record = decision_store.upsert_capability_contract(
            kind="tool",
            name=tool.name,
            tenant_id=tenant_id,
            version=digest[-12:],
            content_digest=digest,
            capabilities=payload,
            source="filesystem",
            status="draft",
        )
        if activate and record.status != "active":
            record = decision_store.set_capability_contract_status(
                record.contract_id, "active"
            )
        synced.append(record)

    return synced


def get_active_capabilities(
    kind: CapabilityKind,
    *,
    tenant_id: str | None = None,
    store: DecisionStore | None = None,
) -> list[CapabilityContractRecord]:
    decision_store = store or get_decision_store()
    page = decision_store.list_capability_contracts(
        kind=kind,
        status="active",
        tenant_id=tenant_id,
        limit=500,
    )
    return list(page.items)


def active_capability_map(
    kind: CapabilityKind,
    *,
    tenant_id: str | None = None,
    store: DecisionStore | None = None,
) -> dict[str, dict[str, Any]]:
    """Name → capabilities dict for governance evaluation overlays."""
    return {
        item.name: dict(item.capabilities)
        for item in get_active_capabilities(
            kind, tenant_id=tenant_id, store=store
        )
    }


def resolve_execution_capability_digests(
    *,
    agent: str = "",
    tenant_id: str = "",
    store: DecisionStore | None = None,
) -> tuple[str, str]:
    """Return (agent_digest, tools_digest) for active contracts.

    Empty strings mean no active pin (legacy / unbound). ``tools_digest`` is a
    canonical digest of ``{tool_name: content_digest}`` for tools listed on the
    active agent contract (or all active tools when the agent has no tool list).
    """
    decision_store = store or get_decision_store()
    agent_name = (agent or "").strip()
    tenant = (tenant_id or "").strip()
    agent_digest = ""
    tool_names: list[str] = []
    if agent_name:
        page = decision_store.list_capability_contracts(
            kind="agent",
            status="active",
            name=agent_name,
            tenant_id=tenant or None,
            limit=1,
        )
        if page.items:
            agent_digest = page.items[0].content_digest or ""
            caps = page.items[0].capabilities or {}
            raw_tools = caps.get("tools") or caps.get("allowed_tools") or []
            if isinstance(raw_tools, list):
                tool_names = [str(item) for item in raw_tools if item]

    tool_records = get_active_capabilities(
        "tool", tenant_id=tenant or None, store=decision_store
    )
    tool_digest_map = {
        item.name: item.content_digest
        for item in tool_records
        if item.content_digest
    }
    if tool_names:
        selected = {
            name: tool_digest_map[name]
            for name in sorted(tool_names)
            if name in tool_digest_map
        }
    else:
        selected = {name: tool_digest_map[name] for name in sorted(tool_digest_map)}
    if not selected:
        return agent_digest, ""
    tools_digest = _canonical_digest(selected)
    return agent_digest, tools_digest
