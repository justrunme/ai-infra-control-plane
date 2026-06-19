output "server_id" {
  description = "Hetzner Cloud server ID."
  value       = hcloud_server.k3s.id
}

output "server_name" {
  description = "Hetzner Cloud server name."
  value       = hcloud_server.k3s.name
}

output "ipv4_address" {
  description = "Public IPv4 address of the k3s node."
  value       = hcloud_server.k3s.ipv4_address
}

output "ssh_command" {
  description = "SSH command for accessing the k3s node."
  value       = "ssh root@${hcloud_server.k3s.ipv4_address}"
}

output "kubeconfig_command" {
  description = "Command to fetch kubeconfig after cloud-init finishes."
  value       = "ssh root@${hcloud_server.k3s.ipv4_address} sudo cat /etc/rancher/k3s/k3s.yaml"
}

output "kubectl_nodes_command" {
  description = "Command to verify the k3s node from the server."
  value       = "ssh root@${hcloud_server.k3s.ipv4_address} sudo k3s kubectl get nodes -o wide"
}
