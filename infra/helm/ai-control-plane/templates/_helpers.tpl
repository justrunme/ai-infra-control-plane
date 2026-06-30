{{- define "ai-control-plane.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ai-control-plane.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "ai-control-plane.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ai-control-plane.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ai-control-plane.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ai-control-plane.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "ai-control-plane.labels" -}}
helm.sh/chart: {{ include "ai-control-plane.chart" . }}
{{ include "ai-control-plane.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: ai-infra-control-plane
{{- end -}}

{{- define "ai-control-plane.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "ai-control-plane.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}
