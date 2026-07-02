#!/usr/bin/env python3
"""Scan prompts for PII, secrets, and injection patterns before inference."""

from __future__ import annotations

import re
from typing import Any

PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email_address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    (
        "phone_number",
        re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?){2}\d{4}\b"),
    ),
    (
        "ssn_like",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    ),
]

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    (
        "generic_api_key",
        re.compile(r"\b(?:api[_-]?key|secret|token)\s*[:=]\s*\S{8,}\b", re.I),
    ),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}\b", re.I)),
]

INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore_instructions",
        re.compile(r"ignore (all )?(previous|prior) instructions", re.I),
    ),
    ("system_override", re.compile(r"you are now (?:a|an) ", re.I)),
    (
        "prompt_leak",
        re.compile(r"reveal (?:the )?(system prompt|hidden instructions)", re.I),
    ),
    ("jailbreak_roleplay", re.compile(r"do anything now|DAN mode|developer mode", re.I)),
]


def _find_matches(
    text: str, patterns: list[tuple[str, re.Pattern[str]]]
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for label, pattern in patterns:
        if pattern.search(text):
            findings.append({"type": label})
    return findings


def evaluate_prompt_security(request: dict[str, Any]) -> dict[str, Any]:
    prompt_text = str(request.get("prompt_text", "")).strip()
    if not prompt_text:
        return {
            "decision": "allow",
            "reasons": ["no prompt text to scan"],
            "findings": [],
        }

    findings: list[dict[str, str]] = []
    findings.extend(_find_matches(prompt_text, PII_PATTERNS))
    findings.extend(_find_matches(prompt_text, SECRET_PATTERNS))
    findings.extend(_find_matches(prompt_text, INJECTION_PATTERNS))

    if not findings:
        return {
            "decision": "allow",
            "reasons": ["prompt security checks passed"],
            "findings": [],
        }

    labels = sorted({item["type"] for item in findings})
    block_on_pii = bool(request.get("sensitive_data", False))
    has_injection = any(
        item["type"] in {label for label, _ in INJECTION_PATTERNS} for item in findings
    )
    has_secret = any(
        item["type"] in {label for label, _ in SECRET_PATTERNS} for item in findings
    )
    pii_labels = {label for label, _ in PII_PATTERNS}
    has_pii = any(item["type"] in pii_labels for item in findings)

    if has_injection or has_secret or (has_pii and block_on_pii):
        return {
            "decision": "block",
            "reasons": [f"prompt security detected: {', '.join(labels)}"],
            "findings": findings,
        }

    return {
        "decision": "warn",
        "reasons": [f"prompt security warning: {', '.join(labels)}"],
        "findings": findings,
    }
