{{/*
OpenOncology Helm helpers
*/}}

{{- define "openoncology.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "openoncology.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "openoncology.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ include "openoncology.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "openoncology.selectorLabels" -}}
app.kubernetes.io/name: {{ include "openoncology.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "openoncology.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "openoncology.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/* Database URL from postgresql sub-chart */}}
{{- define "openoncology.databaseUrl" -}}
postgresql+asyncpg://{{ .Values.postgresql.auth.username }}:$(DB_PASSWORD)@{{ .Release.Name }}-postgresql:5432/{{ .Values.postgresql.auth.database }}
{{- end }}

{{/* Redis URL from redis sub-chart */}}
{{- define "openoncology.redisUrl" -}}
redis://{{ .Release.Name }}-redis-master:6379/0
{{- end }}
