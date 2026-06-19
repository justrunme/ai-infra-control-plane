package main

workload_kinds := {"Pod", "Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"}

deny contains msg if {
	is_workload
	container := containers[_]
	container.securityContext.privileged == true
	msg := sprintf("%s/%s container %q must not run privileged", [input.kind, input.metadata.name, container.name])
}

deny contains msg if {
	is_workload
	container := containers[_]
	endswith(container.image, ":latest")
	msg := sprintf("%s/%s container %q must not use the latest image tag", [input.kind, input.metadata.name, container.name])
}

deny contains msg if {
	is_workload
	container := containers[_]
	not container.resources.requests.cpu
	msg := sprintf("%s/%s container %q must set CPU requests", [input.kind, input.metadata.name, container.name])
}

deny contains msg if {
	is_workload
	container := containers[_]
	not container.resources.requests.memory
	msg := sprintf("%s/%s container %q must set memory requests", [input.kind, input.metadata.name, container.name])
}

deny contains msg if {
	is_workload
	container := containers[_]
	not container.resources.limits.cpu
	msg := sprintf("%s/%s container %q must set CPU limits", [input.kind, input.metadata.name, container.name])
}

deny contains msg if {
	is_workload
	container := containers[_]
	not container.resources.limits.memory
	msg := sprintf("%s/%s container %q must set memory limits", [input.kind, input.metadata.name, container.name])
}

deny contains msg if {
	is_workload
	container := containers[_]
	not container.securityContext.readOnlyRootFilesystem == true
	msg := sprintf("%s/%s container %q should set readOnlyRootFilesystem=true", [input.kind, input.metadata.name, container.name])
}

deny contains msg if {
	is_workload
	container := containers[_]
	not run_as_non_root(container)
	msg := sprintf("%s/%s container %q must run as non-root", [input.kind, input.metadata.name, container.name])
}

is_workload if {
	input.kind in workload_kinds
}

containers contains container if {
	container := pod_spec.containers[_]
}

containers contains container if {
	container := pod_spec.initContainers[_]
}

run_as_non_root(container) if {
	container.securityContext.runAsNonRoot == true
}

run_as_non_root(container) if {
	not container.securityContext.runAsNonRoot == false
	pod_spec.securityContext.runAsNonRoot == true
}

pod_spec := input.spec if {
	input.kind == "Pod"
}

pod_spec := input.spec.template.spec if {
	input.kind == "Deployment"
}

pod_spec := input.spec.template.spec if {
	input.kind == "StatefulSet"
}

pod_spec := input.spec.template.spec if {
	input.kind == "DaemonSet"
}

pod_spec := input.spec.template.spec if {
	input.kind == "Job"
}

pod_spec := input.spec.jobTemplate.spec.template.spec if {
	input.kind == "CronJob"
}
