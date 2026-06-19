package main

test_allows_hardened_deployment if {
	count(deny) == 0 with input as hardened_deployment
}

test_denies_privileged_containers if {
	violations := deny with input as privileged_deployment
	contains_message(violations, "must not run privileged")
}

test_denies_latest_image_tag if {
	violations := deny with input as latest_image_deployment
	contains_message(violations, "must not use the latest image tag")
}

test_denies_missing_resources if {
	violations := deny with input as missing_resources_deployment
	contains_message(violations, "must set CPU requests")
	contains_message(violations, "must set memory requests")
	contains_message(violations, "must set CPU limits")
	contains_message(violations, "must set memory limits")
}

test_recommends_read_only_root_filesystem if {
	violations := deny with input as writable_root_filesystem_deployment
	contains_message(violations, "should set readOnlyRootFilesystem=true")
}

test_requires_non_root_runtime if {
	violations := deny with input as root_deployment
	contains_message(violations, "must run as non-root")
}

test_allows_pod_level_non_root_runtime if {
	count(deny) == 0 with input as pod_level_non_root_deployment
}

contains_message(violations, expected) if {
	message := violations[_]
	contains(message, expected)
}

hardened_deployment := {
	"apiVersion": "apps/v1",
	"kind": "Deployment",
	"metadata": {"name": "control-api"},
	"spec": {"template": {"spec": {"containers": [hardened_container]}}},
}

pod_level_non_root_deployment := {
	"apiVersion": "apps/v1",
	"kind": "Deployment",
	"metadata": {"name": "control-api"},
	"spec": {"template": {"spec": {
		"securityContext": {"runAsNonRoot": true},
		"containers": [object.union(hardened_container, {"securityContext": {"readOnlyRootFilesystem": true}})],
	}}},
}

privileged_deployment := set_security_context({"privileged": true, "readOnlyRootFilesystem": true, "runAsNonRoot": true})

latest_image_deployment := set_container("image", "ghcr.io/justrunme/ai-infra-control-plane:latest")

missing_resources_deployment := set_containers([object.remove(hardened_container, ["resources"])])

writable_root_filesystem_deployment := set_containers([object.union(
	object.remove(hardened_container, ["securityContext"]),
	{"securityContext": {"runAsNonRoot": true}},
)])

root_deployment := set_containers([object.union(
	object.remove(hardened_container, ["securityContext"]),
	{"securityContext": {"readOnlyRootFilesystem": true, "runAsNonRoot": false}},
)])

hardened_container := {
	"name": "control-api",
	"image": "ghcr.io/justrunme/ai-infra-control-plane:v0.1.0",
	"securityContext": {
		"readOnlyRootFilesystem": true,
		"runAsNonRoot": true,
	},
	"resources": {
		"requests": {
			"cpu": "100m",
			"memory": "128Mi",
		},
		"limits": {
			"cpu": "500m",
			"memory": "512Mi",
		},
	},
}

set_container(key, value) := deployment if {
	container := object.union(hardened_container, {key: value})
	deployment := set_containers([container])
}

set_security_context(security_context) := deployment if {
	container := object.union(hardened_container, {"securityContext": security_context})
	deployment := set_containers([container])
}

set_containers(containers) := deployment if {
	deployment := {
		"apiVersion": "apps/v1",
		"kind": "Deployment",
		"metadata": {"name": "control-api"},
		"spec": {"template": {"spec": {"containers": containers}}},
	}
}
