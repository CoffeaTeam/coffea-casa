# Partually based on https://github.com/dask/dask-docker/blob/master/base/Dockerfile
FROM jupyter/minimal-notebook:latest

###
### Jupyterlab
###
# Add extra plugins
RUN jupyter labextension install --no-build @jupyter-widgets/jupyterlab-manager
RUN jupyter labextension install --no-build @jupyterlab/git
RUN jupyter labextension install --no-build @jupyterlab/github
RUN jupyter labextension install --no-build dask-labextension

# Dask extention (looks like it is not available in the image)
RUN pip install \
  dask_labextension \
  jupyterlab_git \
  jupyterlab_github

# Enable the serverextensions that do not use the conf.d approach
RUN jupyter serverextension enable --sys-prefix jupyterlab_git

# Build JupyterLab.
RUN jupyter lab build --dev-build=False && jupyter lab clean && \
    npm cache clean --force && \
    rm -rf /home/$NB_USER/.cache/yarn && \
    rm -rf /home/$NB_USER/.node-gyp && \
    fix-permissions $CONDA_DIR && \
    fix-permissions /home/$NB_USER

# sed -i -e "s|DASK_DASHBOARD_URL|${JUPYTERHUB_SERVICE_PREFIX}proxy/8787|g" jupyterlab-workspace.json
# export DASK_DISTRIBUTED__DASHBOARD__LINK="${JUPYTERHUB_SERVICE_PREFIX}proxy/8787/status"
COPY jupyterlab-workspace.json $HOME/jupyterlab-workspace.json
RUN jupyter lab workspaces import $HOME/jupyterlab-workspace.json

# labextension.yml + kubernetes.yml
COPY dask_config.yml $CONDA_DIR/etc/dask.yml
COPY dask_config.yml $HOME/.config/dask/dask.yml
COPY kubernetes.yml  $HOME/.config/dask/kubernetes.yml
COPY labextension.yml  $HOME/.config/dask/labextension.yml

#Preparing patches
COPY patches/ $HOME/

###
### Dask
###
USER root
#Script that helps to work out missing packages without editing Docker image
COPY prepare.sh /usr/bin/prepare.sh

# Update repositories
RUN apt-get update

# EGI CA certificates
# (as well as xrootd dependencies: libssl-dev zlib1g-dev uuid-dev)
RUN apt-get install gnupg2 libssl-dev zlib1g-dev uuid-dev openssh-client python-setuptools -y \
    && wget -q -O - https://dist.eugridpma.info/distribution/igtf/current/GPG-KEY-EUGridPMA-RPM-3 | apt-key add - \
    && echo "deb http://repository.egi.eu/sw/production/cas/1/current egi-igtf core" >> /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y ca-policy-egi-core \
    && apt-get purge -y gnupg2 \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

USER $NB_UID

# Dask dependencies and HTCondor
# https://anaconda.org/conda-forge/htcondor
RUN conda install --yes --freeze-installed \
    -c conda-forge \
    # ->Dask image
    # IMPORTANT: Python 3.8 doesn't work with coffea
    # python==3.8 \
    python-blosc \
    cytoolz \
    #dask==2.16.0 \ -> we hope dask will be installed with dependencies later
    lz4 \
    nomkl \
    numpy==1.18.1 \
    pandas==1.0.1 \
    tini==0.18.0 \
    # Coffea-casa extras
    bokeh \
    # IMPORTANT: we need apply mini patches -> building from scratch
    #distributed \
    #dask-jobqueue \
    # IMPORTANT: coffea-casa dependencies (in JH we build xrootd from scratch)
    # comment: we need to build it from scratch because we use need  it for xrdcl-authz-plugin build as well
    #xrootd==4.11.2 \ 
    htcondor \
    # Extra packages
    matplotlib==3.2.1 \
    numba==0.48.0 \
    && conda clean -tipsy \
    && find /opt/conda/ -type f,l -name '*.a' -delete \
    && find /opt/conda/ -type f,l -name '*.pyc' -delete \
    && find /opt/conda/ -type f,l -name '*.js.map' -delete \
    && find /opt/conda/lib/python*/site-packages/bokeh/server/static -type f,l -name '*.js' -not -name '*.min.js' -delete \
    && rm -rf /opt/conda/pkgs \
    && conda clean -afy

# Coffea
RUN pip install --no-cache-dir \
    setuptools \
    #dask-jobqueue==0.7.1 \
    xxhash==1.3.0 \
    coffea==0.6.39 \
    # Brian and Nicks scripts dependencies
    cryptography \
    pymacaroons \
    kubernetes \
    jwt \
    # xrootd plugin compilation
    cmake

# Dask dependencies that needs to be patched (hopefully is will pull dask as well)
RUN cd /tmp && \
    git clone https://github.com/dask/dask-jobqueue.git && \
    cd dask-jobqueue && \
    #>>> dask_jobqueue._version.version_json
    #'\n{\n "date": "2020-03-26T03:47:05+0100",\n "dirty": false,\n "error": null,\n "full-revisionid": "1033e4d56e363cc512f9c37d1ca51a0abbb0e562",\n "version": "0.7.1"\n}\n'
    git checkout tags/0.7.1 &&\
    git apply /home/$NB_USER/dask_jobqueue-bbockelman.patch && \
    python setup.py install

# Dask dependencies that needs to be patched (hopefully is will pull dask as well)
RUN cd /tmp && \
    git clone https://github.com/dask/distributed.git && \
    cd distributed && \
    #>>> distributed._version.version_json
    #'\n{\n "date": "2020-05-08T15:59:42-0500",\n "dirty": false,\n "error": null,\n "full-revisionid": "f66eda86c36e2f0b0496552c496736baf80c1c1e",\n "version": "2.16.0"\n}\n'
    git checkout tags/2.16.0 &&\
    git apply /home/$NB_USER/distributed-bbockelman.patch && \
    python setup.py install

# We need to build xrootd and xrdcl-authz-plugin from scratch :( - xrootd looks like is not distributed on Ubuntu
RUN cd /tmp && \
    git clone https://github.com/xrootd/xrootd.git && \
    cd xrootd && \
    git checkout v4.12.1 &&\
    # Patch is used for 5.0.0-HEAD
    # git apply /home/$NB_USER/xrootd-pr1199.patch && \
    mkdir build && \
    cd  build && \
    cmake /tmp/xrootd -DCMAKE_INSTALL_PREFIX=/usr -DPYTHON_EXECUTABLE=/opt/conda/bin/python && \
    make -j4

USER root
RUN cd /tmp/xrootd/build && make install
    #cd /tmp && \
    #rm -rf xrootd

USER $NB_UID
RUN cd /tmp && \
    git clone https://github.com/bbockelm/xrdcl-authz-plugin.git && \
    cd xrdcl-authz-plugin && \
    mkdir build && \
    cd  build && \
    cmake /tmp/xrdcl-authz-plugin -DCMAKE_INSTALL_PREFIX=/usr && \
    make

USER root
RUN cd /tmp/xrdcl-authz-plugin/build && make install
    #cd /tmp && \
    #rm -rf xrdcl-authz-plugin

# Add job spool directory for HTCondor
RUN mkdir /var/lib/condor && \
    mkdir -p $HOME/.condor/tokens.d && \
    mkdir -p /etc/condor/config.d
# Add HTCondor configuration files
COPY condor_config /etc/condor/
# Copy configuration files (currently all, to be optimised)
COPY config.d  /etc/condor/config.d/

# Tokens setup (moved to k8s)
# https://github.com/oshadura/coffea-casa/issues/2
# UGLY HACK!!!
#RUN sed -i '4imkdir -p /home/jovyan/.condor/tokens.d/ && cp /etc/cmsaf-secrets/condor_token /home/jovyan/.condor/tokens.d/condor_token' /usr/local/bin/start-notebook.sh   

RUN groupadd -r condor && \
    useradd -r -g condor -d /var/lib/condor -s /sbin/nologin condor

#change group for user $NB_USER
#ERROR: Submitting jobs as user/group 0 (root) is not allowed for security reasons.
# it configured from kubernetes side and updated in docker container to match it
RUN groupadd 1000 && usermod -g 1000 $NB_USER

# Dask environment
# TBD: should be changed to UNL home dir
# TBD: mount /hadoop (no need for now)
RUN mkdir /opt/app
RUN chown -R jovyan:1000 /opt/app

WORKDIR /opt/app
USER $NB_UID

# Use bash login shell for entrypoint in order
# to automatically source user's .bashrc
CMD ["bash", "-l", "-c", "'/usr/local/bin/start-notebook.sh'"]
