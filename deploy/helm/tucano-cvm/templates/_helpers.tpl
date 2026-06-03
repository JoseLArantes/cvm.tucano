{{/*
Expand the name of the chart.
*/}}
{{- define "tucano-cvm.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "tucano-cvm.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "tucano-cvm.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "tucano-cvm.labels" -}}
helm.sh/chart: {{ include "tucano-cvm.chart" . }}
{{ include "tucano-cvm.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "tucano-cvm.selectorLabels" -}}
app.kubernetes.io/name: {{ include "tucano-cvm.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Secret name used by application components.
*/}}
{{- define "tucano-cvm.appSecretName" -}}
{{- required "Set appSecret.name to an existing Kubernetes secret." .Values.appSecret.name }}
{{- end }}

{{/*
ConfigMap name used by application components.
*/}}
{{- define "tucano-cvm.configMapName" -}}
{{- printf "%s-env" (include "tucano-cvm.fullname" .) }}
{{- end }}
