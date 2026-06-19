terraform {
  required_version = ">= 1.6.0"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
  }
}

locals {
  labels = merge(
    {
      project = "ai-infra-control-plane"
      role    = "k3s-bootstrap"
    },
    var.labels,
  )
}

resource "hcloud_server" "k3s" {
  name        = var.name
  image       = var.image
  server_type = var.server_type
  location    = var.location
  ssh_keys    = var.ssh_key_names
  labels      = local.labels

  user_data = templatefile("${path.module}/templates/cloud-init.yaml.tftpl", {
    k3s_channel      = var.k3s_channel
    k3s_exec         = var.k3s_exec
    kubeconfig_group = var.kubeconfig_group
  })

  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }
}
