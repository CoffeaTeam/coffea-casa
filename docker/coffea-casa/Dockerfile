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
RUN apt-get install gnupg2 libssl-dev -y \
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
    dask==2.12.0 \
    distributed==2.12.0 \
    dask-kubernetes \
    dask-jobqueue \
    matplotlib==3.2.1 \
    lz4==3.0.2 \
    numba==0.48.0 \
    numpy==1.18.1 \
    pandas==1.0.3 \
    python-blosc==1.8.3 \
    scipy==1.4.1 \
    tini==0.18.0 \
    xrootd==4.11.2 \
    htcondor \
    && conda clean -afy

# Coffea
RUN pip install --no-cache-dir \
    #dask-jobqueue==0.7.1 \
    xxhash==1.3.0 \
    coffea==0.6.39 \
    cryptography \
    pymacaroons \
    kubernetes \
    jwt

USER root

# Dask environment
# TBD: should be changed to UNL home dir
RUN mkdir /opt/app
RUN chown -R jovyan:root /opt/app
#TBD: mount /hadoop?

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
RUN usermod -g condor $NB_USER

WORKDIR /opt/app
USER $NB_UID

#ENTRYPOINT ["tini", "-g", "/usr/bin/prepare.sh"]
#ENTRYPOINT ["tini", "-g", "--"]

# Use bash login shell for entrypoint in order
# to automatically source user's .bashrc
CMD ["bash", "-l", "-c", "'start-notebook.sh'"]
