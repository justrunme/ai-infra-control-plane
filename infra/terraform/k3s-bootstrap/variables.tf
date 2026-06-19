variable "name" {
  description = "Hetzner Cloud server name."
  type        = string
  default     = "ai-k3s-01"
}

variable "image" {
  description = "Hetzner Cloud image used for the k3s node."
  type        = string
  default     = "ubuntu-24.04"
}

variable "server_type" {
  description = "Hetzner Cloud server type."
  type        = string
  default     = "cx32"
}

variable "location" {
  description = "Hetzner Cloud datacenter location."
  type        = string
  default     = "fsn1"
}

variable "ssh_key_names" {
  description = "Existing Hetzner Cloud SSH key names allowed to access the node."
  type        = list(string)
  default     = []
}

variable "labels" {
  description = "Additional labels to attach to the server."
  type        = map(string)
  default     = {}
}

variable "k3s_channel" {
  description = "k3s install channel passed to the official install script."
  type        = string
  default     = "stable"
}

variable "k3s_exec" {
  description = "Additional k3s server arguments."
  type        = string
  default     = "server --disable traefik"
}

variable "kubeconfig_group" {
  description = "Linux group that can read the generated k3s kubeconfig."
  type        = string
  default     = "adm"
}
