# Read provider and gateway secrets used by the AI Infrastructure OS.
path "secret/data/ai-platform/*" {
  capabilities = ["read"]
}

# Optional: issue short-lived tokens for runtime workloads.
path "auth/token/create" {
  capabilities = ["create", "update"]
}
