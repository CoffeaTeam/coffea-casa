{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "coffea-casa.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "coffea-casa.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "coffea-casa.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Traefik name
*/}}
{{- define "coffea-casa.traefikName" -}}
{{ include "coffea-casa.fullname" . | printf "traefik-%s" | trunc 63 | trimSuffix "-" }}
{{- end -}}

{{/*
HTCondor secret
*/}}
{{- define "htcondor.condor_token" -}}
  {{ if .Values.controller.adminPassword -}}
    {{- .Values.controller.adminPassword | b64enc | quote }}
  {{- else -}}
    {{- $secret := (lookup "v1" "Secret" .Release.Namespace (include "coffea-casa.fullname" .)).data -}}
    {{- if $secret -}}
      {{/*
        Reusing current password since secret exists
      */}}
      {{- index $secret default "condor-token" -}}
    {{- else -}}
      {{/*
          Generate new password
      */}}
      {{- randAlphaNum 22 | b64enc | quote }}
    {{- end -}}
  {{- end -}}
{{- end -}}

{{/*
XCache secret
*/}}
{{- define "xcache.xcache_token" -}}
  {{ if .Values.xcache.xcache_token -}}
    {{- .Values.xcache.xcache_token | b64enc | quote }}
  {{- else -}}
    {{- $secret := (lookup "v1" "Secret" .Release.Namespace (include "coffea-casa.fullname" .)).data.xcache_token -}}
    {{- if $secret -}}
      {{/*
        Reusing current password since secret exists
      */}}
      {{- index $secret default "xcache_token" -}}
    {{- else -}}
      {{/*
          Generate new password
      */}}
      {{- randAlphaNum 22 | b64enc | quote }}
    {{- end -}}
  {{- end -}}
{{- end -}}