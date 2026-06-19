{{- define "ai-control-plane.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ai-control-plane.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "ai-control-plane.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

