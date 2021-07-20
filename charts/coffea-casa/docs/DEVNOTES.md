# Development notes: Minikube

Minikube runs a single-node Kubernetes cluster inside a Virtual Machine (VM) on your laptop. For more information on minikube, see the [Minikube documentation](https://kubernetes.io/docs/setup/learning-environment/minikube/).


This document explains on how to deploy coffea-casa using minikube as a provider.

# Quick Start

1. For installing minikube - https://kubernetes.io/docs/tasks/tools/install-minikube/
2. Minikube Documentation - https://minikube.sigs.k8s.io/docs/overview/

# Basic Commands for Minikube

- Start a cluster by running:
 ```minikube start```

- Access the Kubernetes Dashboard running within the minikube cluster:
 ```minikube dashboard```

- Stop your local minikube cluster:
 ```minikube stop```

- Delete your local cluster:
```minikube delete```

Start minikube with at least 4 CPU’s and 10GB memory for complete coffea-casa deployment. As per the need increase the limits of minikube.

# How to deploy coffea-casa

Use `values.yaml` to deploy coffea-casa which is available in the charts/coffea-casa) directory. 

Create namespace:

``` kubectl create namespace coffea-casa ```

Example helm command to test:

```helm install --dry-run --debug coffea-casa coffea-casa```

```
~ helm dependency update
Getting updates for unmanaged Helm repositories...
...Successfully got an update from the "https://jupyterhub.github.io/helm-chart/" chart repository
Hang tight while we grab the latest from your chart repositories...
...Successfully got an update from the "ssl-hep" chart repository
...Successfully got an update from the "daskgateway" chart repository
Update Complete. ⎈Happy Helming!⎈
Saving 2 charts
Downloading jupyterhub from repo https://jupyterhub.github.io/helm-chart/
Downloading servicex from repo https://ssl-hep.github.io/ssl-helm-charts/
Deleting outdated charts```

Example helm command to test:

```helm install --dry-run --debug coffea-casa coffea-casa```

Example helm command to deploy:
	
```~ helm upgrade --install coffea-casa charts/coffea-casa/  --namespace coffea-casa --values charts/coffea-casa/values.yaml --values charts/coffea-casa/secrets.yaml```

