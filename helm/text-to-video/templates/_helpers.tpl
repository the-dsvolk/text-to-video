{{/*
Expand the name of the chart.
*/}}
{{- define "text-to-video.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "text-to-video.fullname" -}}
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
{{- define "text-to-video.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "text-to-video.labels" -}}
helm.sh/chart: {{ include "text-to-video.chart" . }}
{{ include "text-to-video.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "text-to-video.selectorLabels" -}}
app.kubernetes.io/name: {{ include "text-to-video.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
FastAPI Gateway labels
*/}}
{{- define "text-to-video.fastapi.labels" -}}
{{ include "text-to-video.labels" . }}
app.kubernetes.io/component: fastapi-gateway
{{- end }}

{{/*
FastAPI Gateway selector labels
*/}}
{{- define "text-to-video.fastapi.selectorLabels" -}}
{{ include "text-to-video.selectorLabels" . }}
app.kubernetes.io/component: fastapi-gateway
{{- end }}

{{/*
BentoML service labels
*/}}
{{- define "text-to-video.bento.labels" -}}
{{ include "text-to-video.labels" . }}
app.kubernetes.io/component: bento-service
{{- end }}

{{/*
BentoML service selector labels
*/}}
{{- define "text-to-video.bento.selectorLabels" -}}
{{ include "text-to-video.selectorLabels" . }}
app.kubernetes.io/component: bento-service
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "text-to-video.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "text-to-video.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the namespace name
*/}}
{{- define "text-to-video.namespace" -}}
{{- if .Values.namespace.create }}
{{- .Values.namespace.name }}
{{- else }}
{{- .Release.Namespace }}
{{- end }}
{{- end }}

{{/*
Create image pull secrets
*/}}
{{- define "text-to-video.imagePullSecrets" -}}
{{- if .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- range .Values.global.imagePullSecrets }}
  - name: {{ . }}
{{- end }}
{{- end }}
{{- end }}