{{- define "ribdigi.name" -}}
ribdigi
{{- end -}}

{{- define "ribdigi.backend.labels" -}}
app: ribdigi-backend
app.kubernetes.io/name: ribdigi-backend
app.kubernetes.io/part-of: ribdigi
{{- end -}}

{{- define "ribdigi.frontend.labels" -}}
app: ribdigi-frontend
app.kubernetes.io/name: ribdigi-frontend
app.kubernetes.io/part-of: ribdigi
{{- end -}}

{{- define "ribdigi.celeryWorker.labels" -}}
app: ribdigi-celery-worker
app.kubernetes.io/name: ribdigi-celery-worker
app.kubernetes.io/part-of: ribdigi
{{- end -}}

{{- define "ribdigi.celeryBeat.labels" -}}
app: ribdigi-celery-beat
app.kubernetes.io/name: ribdigi-celery-beat
app.kubernetes.io/part-of: ribdigi
{{- end -}}
