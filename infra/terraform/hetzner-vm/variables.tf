variable "name" {
  type    = string
  default = "ai-worker-01"
}

variable "image" {
  type    = string
  default = "ubuntu-24.04"
}

variable "server_type" {
  type    = string
  default = "cx22"
}

variable "location" {
  type    = string
  default = "fsn1"
}

variable "ssh_key_names" {
  type    = list(string)
  default = []
}

