# k3s Bootstrap Example

This Terraform example provisions a single Hetzner Cloud VM and installs k3s through cloud-init. It is intended as a small end-to-end platform bootstrap path for the AI Infrastructure Control Plane.

The example is deliberately manual. It shows the infrastructure shape, but it does not run `terraform apply` from CI or automation.

## What It Creates

- One Hetzner Cloud server for a lightweight k3s control plane.
- Cloud-init bootstrap that installs k3s from the official install script.
- A kubeconfig retrieval command.
- A `kubectl get nodes -o wide` verification command.

## Requirements

- Terraform `>= 1.6.0`.
- A Hetzner Cloud API token available as `HCLOUD_TOKEN`.
- At least one existing Hetzner Cloud SSH key name.

## Usage

Create a local variables file:

```hcl
ssh_key_names = ["your-hetzner-ssh-key"]
```

Initialize and review the plan:

```sh
terraform init
terraform plan -var-file=local.tfvars
```

Apply only from a confirmed local environment:

```sh
terraform apply -var-file=local.tfvars
```

After cloud-init finishes, verify k3s from the server:

```sh
$(terraform output -raw kubectl_nodes_command)
```

Fetch the kubeconfig:

```sh
$(terraform output -raw kubeconfig_command) > k3s.yaml
```

When using the kubeconfig from a workstation, replace `127.0.0.1` or the internal server value in `k3s.yaml` with the `ipv4_address` output.

## Optional Argo CD Bootstrap

Once the cluster is reachable, the next manual step is to install Argo CD and apply the repository application manifest:

```sh
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f ../../argocd/application.yaml
```

This keeps GitOps bootstrap separate from VM provisioning while still showing the end-to-end deployment path:

Terraform VM -> cloud-init -> k3s -> Argo CD -> Helm chart.

## Notes

- The default `k3s_exec` disables Traefik so ingress can be added intentionally later.
- This is a single-node bootstrap example, not a highly available production cluster.
- Destroying this stack deletes the VM and the k3s cluster state stored on it.
