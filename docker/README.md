## Coffea-casa Docker images: UNL-specific and custom


### Coffea-casa Dask Base Scheduler image (without UNL specific settings)

To build and test locally:

```
docker build -t hub.opensciencegrid.org/coffea-casa/cc-base-ubuntu:latest  -f Dockerfile.cc-base-ubuntu
```

### Coffea-casa Dask Scheduler (with UNL specific settings)

To build and test locally (with UNL specific settings, and only after was built Dask Base Scheduler image):

```
docker build -t hub.opensciencegrid.org/coffea-casa/cc-ubuntu:latest  -f Dockerfile.cc-base-ubuntu
```

### Coffea-casa Dask Base Scheduler CC7 image (without UNL specific settings)

To build and test locally (with UNL specific settings):

```
docker build -t hub.opensciencegrid.org/coffea-casa/cc-base-centos7:latest  -f Dockerfile.cc-base-centos7
```

### Coffea-casa Dask Scheduler (with UNL specific settings)

To build and test locally (with UNL specific settings and only after was built Dask Base Scheduler CC7 image):

```
docker build -t hub.opensciencegrid.org/coffea-casa/cc-centos7:latest -f Dockerfile.cc-centos7
```

### Coffea-casa Dask Worker CC7

To build and test locally (with UNL specific settings):

```
docker build -t hub.opensciencegrid.org/coffea-casa/cc-analysis-centos7-skyhook:latest -f Dockerfile.cc-analysis-centos7-skyhook
```

### Coffea-casa Dask Worker Ubuntu

To build and test locally (with UNL specific settings):

```
docker build -t hub.opensciencegrid.org/coffea-casa/cc-analysis-ubuntu-skyhook:latest -f Dockerfile.cc-analysis-ubuntu-skyhook
```

### Coffea-casa Dask Worker CC7 (with Skyhook)

To build and test locally (with UNL specific settings and only after was built Dask Worker CC7 image):

```
docker build -t hub.opensciencegrid.org/coffea-casa/cc-analysis-centos7-skyhook:latest -f Dockerfile.cc-analysis-centos7-skyhook
```

### Coffea-casa Dask Worker Ubuntu (with Skyhook)

To build and test locally (with UNL specific settings and only after was built Dask Worker CC7 image):

```
docker build -t hub.opensciencegrid.org/coffea-casa/cc-analysis-ubuntu-skyhook:latest -f Dockerfile.cc-analysis-ubuntu-skyhook
```

## How to build images for different cluster

See below full table of arguments for Scheduler and Worker image:


| Parameter                | Description             | Default        |
| ------------------------ | ----------------------- | -------------- |
|`TAG`| Name of tag in HUB (only for "derived" images) | "development" |
|`PROJECT`| Name of project in HUB (only for "derived" images) | "coffea-casa" |
|`HUB`| Name of Hub (only for "derived" images) | "hub.opensciencegrid.org" |
|`NAME`| Name of Base image (only for "derived" images) | "${PROJECT}/cc-base-ubuntu"|
|`NB_USER` | User for Jupyter notebook (as well for HTCondor) | `cms-jovyan` |
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


### Custom Coffea-casa Base Scheduler image

***Important note:*** please check that TAG values are the same for scheduler and worker image (as well Docker image tags!)

```
docker build 
--build-arg NB_USER="atlas-jovyan" \
--build-arg NB_UID="6440" \
--build-arg NB_GID="11265" \
--build-arg LABEXTENTION_CLUSTER="UNL HTCondor Cluster" \
--build-arg LABEXTENTION_FACTORY_CLASS="CoffeaCasaCluster" \
--build-arg LABEXTENTION_FACTORY_MODULE="coffea_casa" \
--build-arg CONDOR_HOST="red-condor.unl.edu" \
--build-arg COLLECTOR_NAME="Nebraska T2" \
--build-arg UID_DOMAIN="unl.edu" \
--build-arg SCHEDD_HOST="t3.unl.edu" \
 -t hub.opensciencegrid.org/coffea-casa/cc-base-ubuntu:$TAG -f Dockerfile.cc-base-ubuntu
```
### Custom Coffea-casa Dask Scheduler image

***Important note:*** please check that TAG values are the same for scheduler and worker image (as well Docker image tags!)

```
docker build
--build-arg PROJECT="coffea-casa" \
--build-arg TAG="2021.10.28" \
--build-arg HUB="hub.opensciencegrid.org" \
--build-arg XCACHE_HOST="red-xcache1.unl.edu" \
--build-arg CACHE_PREFIX="red-xcache1.unl.edu" \
--build-arg LABEXTENTION_CLUSTER="UNL HTCondor Cluster" \
--build-arg LABEXTENTION_FACTORY_CLASS="CoffeaCasaCluster" \
--build-arg LABEXTENTION_FACTORY_MODULE="coffea_casa" \
--build-arg CONDOR_HOST="red-condor.unl.edu" \
--build-arg COLLECTOR_NAME="Nebraska T2" \
--build-arg UID_DOMAIN="unl.edu" \
--build-arg SCHEDD_HOST="t3.unl.edu" \
-t hub.opensciencegrid.org/coffea-casa/cc-ubuntu:$TAG -f Dockerfile.cc-ubuntu
```

Other build arguments, which are optional to be changed:
```
--build-arg CERT_DIR="/etc/cmsaf-secrets"
--build-arg BEARER_TOKEN_FILE=$CERT_DIR"/xcache_token"
--build-arg DASK_ROOT_CONFIG="/opt/dask"
```

### Custom Coffea-casa Dask Skyhook Scheduler image

***Important note:*** please check that TAG values are the same for scheduler and worker image (as well Docker image tags!)

```
docker build
--build-arg PROJECT="coffea-casa" \
--build-arg TAG="2021.10.28" \
--build-arg HUB="hub.opensciencegrid.org" \
-t hub.opensciencegrid.org/coffea-casa/cc-ubuntu:$TAG -f Dockerfile.cc-ubuntu
```

###  Custom Coffea-casa Dask Base Worker image

***Important note:*** please check that TAG values are the same for scheduler and worker image (as well Docker image tags!)
```
docker build 
--build-arg NB_USER="atlas-jovyan" \
--build-arg NB_UID="6440" \
--build-arg NB_GID="11265" \
--build-arg XCACHE_HOST="red-xcache1.unl.edu" \
--build-arg CACHE_PREFIX="red-xcache1.unl.edu" \
-t hub.opensciencegrid.org/coffea-casa/cc-analysis-ubuntu:$TAG -f Dockerfile.cc-analysis-ubuntu
```

Other build arguments, which are optional to be changed:
```
--build-arg CERT_DIR="/etc/cmsaf-secrets"
--build-arg BEARER_TOKEN_FILE=$CERT_DIR"/xcache_token"
```

###  Custom Coffea-casa Dask Skyhook Worker image

***Important note:*** please check that TAG values are the same for scheduler and worker image (as well Docker image tags!)
```
docker build 
--build-arg PROJECT="coffea-casa" \
--build-arg TAG="2021.10.28" \
--build-arg HUB="hub.opensciencegrid.org" \
-t hub.opensciencegrid.org/coffea-casa/cc-analysis-ubuntu-skyhook:$TAG -f Dockerfile.cc-analysis-ubuntu-skyhook
```
