terraform {
  required_version = ">= 1.6.0"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
  }
}

resource "hcloud_server" "ai_worker" {
  name        = var.name
  image       = var.image
  server_type = var.server_type
  location    = var.location
  ssh_keys    = var.ssh_key_names

  labels = {
    project = "ai-infra-control-plane"
    role    = "ai-worker"
  }
}

output "ipv4_address" {
  value = hcloud_server.ai_worker.ipv4_address
}

