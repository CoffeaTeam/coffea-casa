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
RUN apt-get install gnupg2 libssl-dev zlib1g-dev uuid-dev -y \
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
    # Python 3.8 doesn't work with coffea
    # python==3.8 \
    python-blosc \
    cytoolz \
    dask==2.16.0 \
    lz4 \
    nomkl \
    numpy==1.18.1 \
    pandas==1.0.1 \
    tini==0.18.0 \
    # Coffea-casa extras
    bokeh \
    distributed \
    dask-jobqueue \
    # coffea-casa dependencies (in JH we build xrootd from scratch)
    # cpmment: we need to build it from scratch because we use need  it for xrdcl-authz-plugin build as well
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

# We need to build xrootd and xrdcl-authz-plugin from scratch :( - xrootd is not distributed on Ubuntu
COPY xrootd-pr1199.patch /tmp/xrootd-pr1199.patch

RUN cd /tmp && \
    git clone https://github.com/xrootd/xrootd.git && \
    cd xrootd && \
    git checkout v4.12.1 &&\
    # Patch is used for 5.0.0-HEAD
    # git apply /tmp/xrootd-pr1199.patch && \
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

# Tokens setup
# https://github.com/oshadura/coffea-casa/issues/2

RUN if [ -f "/etc/cmsaf-secrets/condor_token" ]; then cp /etc/cmsaf-secrets/condor_token ~/.condor/tokens.d; fi

RUN groupadd -r condor && \
    useradd -r -g condor -d /var/lib/condor -s /sbin/nologin condor

#change greoup for user $NB_USER
#ERROR: Submitting jobs as user/group 0 (root) is not allowed for security reasons.
# No need to cahnge, it configured from kubernetes side
#RUN usermod -g condor $NB_USER

# Dask environment
# TBD: should be changed to UNL home dir
RUN mkdir /opt/app
RUN chown -R jovyan:condor /opt/app
#TBD: mount /hadoop?

WORKDIR /opt/app
USER $NB_UID


# Use bash login shell for entrypoint in order
# to automatically source user's .bashrc
CMD ["bash", "-l", "-c", "'start-notebook.sh'"]
