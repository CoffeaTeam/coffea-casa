# Coffea-casa Helm Charts


[Helm](https://helm.sh) is needed to be installed to use the `coffea-casa-charts` charts.
(please check Helm's [documentation](https://helm.sh/docs/) to get started).

Once Helm is set up properly, add the repo as follows:

```sh
helm repo add coffea-casa https://coffeateam.github.io/coffea-casa
```

You can then run `helm search repo coffea-casa` to see the charts.

# Prepare Configuration Fils

In this step, we'll prepare a YAML configuration file with the fields required by the Coffea-casa helm chart. It will contain some secret keys, which should not be checked into version control in plaintext.

This secrets should be encoded using kubeseal.

```yaml
# file: secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  creationTimestamp: null
  name: coffea-casa-secrets
  namespace: <<add here namespace>>
data:
  xcache-token: <<xcache-token>>
  condor-token: <<condor-token>>
  client_id: <<CMS OIDC - OAUTH_CLIENT_ID>>
  client_secret: <<CMS OIDC - OAUTH_CLIENT_SECRET>>
```

## Install Coffea-Casa

This example installs into the namespace `coffa-casa`. Make sure you're
in the same directory as the `secrets.yaml` file.

* Edit  values.yaml or create your own file `jhub-values` and `servicex-values.yaml`.

* Generate secrets adding relevant values in `secrets.yaml` and then run:

```console

kubeseal -o yaml -n coffea-casa --cert ~/kubeseal-cert/kubeseal.pem < coffea-casa/secrets.yaml > jhub-secrets.yaml

kubectl create -f jhub-secrets.yaml

```

* Run Helm command:

```console
$ helm upgrade --wait --install \
    coffea-casa coffea-casa/coffea-casa \
    --namespace=coffea-casa \
    --values=jhub-values.yaml
    --values=servicex-values.yaml
```

The output explains how to find the IPs for your JupyterHub.

```console
$ kubectl -n coffea-casa get service proxy-public
```


## Configuration (currently placeholder - TBD)

The following table lists the configurable parameters of the Daskhub chart and their default values.

| Parameter                | Description             | Default        |
| ------------------------ | ----------------------- | -------------- |
| `hub.config.Authenticator.admin_users` | Add a list of user emails that will have admin rights on coffea-csaa jhub | `coffea-casa-dev@cern.ch` |
