# Prompt Governance

Pre-inference prompt scanning in the governance pipeline.

## Pipeline stage

```text
policy_pack → prompt_security → agent_registry → quota → model_registry → ...
```

## Checks

| Class | Examples | Default behavior |
| --- | --- | --- |
| PII | email, phone, SSN-like | Block when `sensitive_data: true` |
| Secrets | AWS keys, GitHub tokens, bearer tokens | Always block |
| Injection | ignore instructions, jailbreak phrases | Always block |

## API

Pass prompt text in the evaluate body:

```bash
curl -sS -X POST http://127.0.0.1:8091/governance/evaluate \
  -H 'content-type: application/json' \
  -d '{
    "team": "platform",
    "namespace": "ai-dev",
    "model": "llama3.1:8b",
    "provider": "ollama",
    "prompt_text": "My email is alice@example.com",
    "sensitive_data": true
  }'
```

The execution plane gateway extracts prompt text from chat `messages` automatically.

## Related

- [Runtime enforcement](runtime-enforcement.md)
