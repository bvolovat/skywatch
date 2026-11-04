{{/* Base name for all resources: the release name, e.g. "skywatch". */}}
{{- define "skywatch.fullname" -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Labels shared by every resource. Usage: include "skywatch.labels" (dict "ctx" . "component" "backend") */}}
{{- define "skywatch.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .ctx.Chart.Name .ctx.Chart.Version }}
app.kubernetes.io/managed-by: {{ .ctx.Release.Service }}
app.kubernetes.io/part-of: skywatch
{{ include "skywatch.selectorLabels" . }}
{{- end -}}

{{/* Immutable selector labels (must never change after the first install). */}}
{{- define "skywatch.selectorLabels" -}}
app.kubernetes.io/name: {{ .component }}
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
{{- end -}}

{{/* Name of the backend Service, used by the frontend to build BACKEND_URL. */}}
{{- define "skywatch.backendName" -}}
{{- printf "%s-backend" (include "skywatch.fullname" .) -}}
{{- end -}}

{{- define "skywatch.frontendName" -}}
{{- printf "%s-frontend" (include "skywatch.fullname" .) -}}
{{- end -}}
