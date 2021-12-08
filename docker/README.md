
# Coffea-casa Docker UNL specific images

## Coffea-casa Dask Scheduler image

To build and test locally (with UNL specific settings):

```
docker build -t coffeateam/coffea-casa:latest coffea-casa
```

```
docker run -it --rm coffeateam/coffea-casa:latest /bin/bash
```

## Coffea-casa Dask Worker

To build and test locally (with UNL specific settings):

```
docker build -t coffeateam/coffea-casa-analysis:latest coffea-casa-analysis
```

```
docker run -it --rm coffeateam/coffea-casa-analysis:latest /bin/bash
```

## Coffea-casa Dask Scheduler CC7 image

To build and test locally (with UNL specific settings):

```
docker build -t coffeateam/coffea-casa-cc7:latest coffea-casa
```

```
docker run -it --rm coffeateam/coffea-casa-cc7:latest /bin/bash
```

## Coffea-casa Dask Worker CC7

To build and test locally (with UNL specific settings):

```
docker build -t coffeateam/coffea-casa-analysis-cc7:latest coffea-casa-analysis
```

```
docker run -it --rm coffeateam/coffea-casa-analysis-cc7:latest /bin/bash
```

## How to build images for different cluster


### How to build generic Coffea-casa Dask Scheduler image


See below full table of arguments for Scheduler and Worker image:


| Parameter                | Description             | Default        |
| ------------------------ | ----------------------- | -------------- |
| `NB_USER` | User for Jupyter notebook (as well for HTCondor) | `cms-jovyan` |
|`NB_UID`| User UID | `6440` |
|`NB_GID`| User GID | `11265` |
|`TAG`| Tag used to sync image for worker configured in Coffea_casa Dask Jobqueue extention | `2021.10.28` |
|`WORKER_IMAGE`| Image name used to sync image for worker configured in Coffea_casa Dask Jobqueue extention | `coffeateam/coffea-casa-analysis` |
|`XCACHE_HOST`| XCache host used for custom Xrootd plugin | `red-xcache1.unl.edu` |
|`CACHE_PREFIX`| XCache prefix used for ServiceX | `red-xcache1.unl.edu` |
|`LABEXTENTION_CLUSTER`| Name of default cluster configured in Coffea_casa Dask Jobqueue extention | `UNL HTCondor Cluster` |
|`LABEXTENTION_FACTORY_CLASS`| Name of class used for Dask Labextention factory and configured in Coffea_casa Dask Jobqueue extention | `CoffeaCasaCluster` |
|`LABEXTENTION_FACTORY_MODULE`| Name of python module used for Dask Labextention factory and configured in Coffea_casa Dask Jobqueue extention | `coffea_casa` |
|`CONDOR_HOST`| HTCondor Condor host | `red-condor.unl.edu` |
|`COLLECTOR_NAME`| HTCondor collector name | `Nebraska T2` |
|`UID_DOMAIN`| Domain | `t3.unl.edu` |
|`SCHEDD_HOST`| HTCondor schedduler host | `t3.unl.edu` |
|`CERT_DIR`| Directory where are generated all secrets (see charts) | `/etc/cmsaf-secrets` |
|`BEARER_TOKEN_FILE`| Bearer token file location (see charts) | `/opt/dask` |
|`DASK_ROOT_CONFIG`| Dask configuration file directory | `/opt/dask` |


#### Custom Coffea-casa Scheduler image

***Important note:*** please check that TAG values are the same for scheduler and worker image (as well Docker image tags!)

```
docker build 
--build-arg NB_USER="atlas-jovyan" \
--build-arg NB_UID="6440" \
--build-arg NB_GID="11265" \
--build-arg TAG="2021.10.28" \
--build-arg WORKER_IMAGE="coffeateam/coffea-casa-analysis" \
--build-arg XCACHE_HOST="red-xcache1.unl.edu" \
--build-arg CACHE_PREFIX="red-xcache1.unl.edu" \
--build-arg LABEXTENTION_CLUSTER="X HTCondor Cluster" \
--build-arg CONDOR_HOST="red-condor.unl.edu" \
--build-arg COLLECTOR_NAME="Nebraska T2" \
--build-arg UID_DOMAIN="unl.edu" \
--build-arg SCHEDD_HOST="t3.unl.edu" \
 -t coffeateam/coffea-casa:$TAG coffea-casa
```

Other build arguments, which are optional to be changed:
```
--build-arg CERT_DIR="/etc/cmsaf-secrets"
--build-arg BEARER_TOKEN_FILE=$CERT_DIR"/xcache_token"
--build-arg DASK_ROOT_CONFIG="/opt/dask"
--build-arg LABEXTENTION_FACTORY_CLASS="CoffeaCasaCluster"
--build-arg LABEXTENTION_FACTORY_MODULE="coffea_casa"
```

####  Custom Coffea-casa Dask Worker image

***Important note:*** please check that TAG values are the same for scheduler and worker image (as well Docker image tags!)
```
docker build 
--build-arg NB_USER="atlas-jovyan" \
--build-arg NB_UID="6440" \
--build-arg NB_GID="11265" \
--build-arg TAG="2021.10.28" \
--build-arg XCACHE_HOST="red-xcache1.unl.edu" \
--build-arg CACHE_PREFIX="red-xcache1.unl.edu" \
 -t coffeateam/coffea-casa-analysis:$TAG coffea-casa-analysis
```

Other build arguments, which are optional to be changed:
```
--build-arg CERT_DIR="/etc/cmsaf-secrets"
--build-arg BEARER_TOKEN_FILE=$CERT_DIR"/xcache_token"
```
