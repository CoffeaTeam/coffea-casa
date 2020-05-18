# Partually based on https://github.com/dask/dask-docker/blob/master/base/Dockerfile
FROM jupyter/minimal-notebook:latest

###
### Jupyterlab
###

# Add extra pluggins
RUN jupyter labextension install --no-build dask-labextension && \
    jupyter labextension install --no-build @jupyter-widgets/jupyterlab-manager && \
    jupyter lab build && \
    jupyter lab clean && \
    npm cache clean --force && \
    rm -rf /home/$NB_USER/.cache/yarn && \
    rm -rf /home/$NB_USER/.node-gyp && \
    fix-permissions $CONDA_DIR && \
    fix-permissions /home/$NB_USER

# sed -i -e "s|DASK_DASHBOARD_URL|${JUPYTERHUB_SERVICE_PREFIX}proxy/8787|g" jupyterlab-workspace.json
# export DASK_DISTRIBUTED__DASHBOARD__LINK="${JUPYTERHUB_SERVICE_PREFIX}proxy/8787/status"
COPY jupyterlab-workspace.json $HOME/jupyterlab-workspace.json
RUN jupyter lab workspaces import $HOME/jupyterlab-workspace.json
# extra dask config
RUN mkdir -p $HOME/.config/dask
#COPY dask.yaml $HOME/.config/dask/dask.yaml
COPY labextension.yml  $HOME/.config/dask/labextension.yml
COPY kubernetes.yml $HOME/.config/dask/kubernetes.yml

###
### Dask
###
USER root
#Script that helps to work out missing packages without editing Docker image
COPY prepare.sh /usr/bin/prepare.sh

# Update repositories
RUN apt-get update

# EGI CA certificates
RUN apt-get install gnupg2 -y \
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
    #bokeh==2.0.0 \
    dask==2.12.0 \
    distributed==2.12.0 \
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
    dask-kubernetes \
    && conda clean -afy

# Coffea
RUN /opt/conda/bin/pip install --no-cache-dir \
    dask-jobqueue==0.7.1 \
    xxhash==1.3.0 \
    coffea==0.6.37

USER root
# Dask environment
RUN mkdir /opt/app
# Add job spool directory for HTCondor
RUN mkdir /var/lib/condor
# Add configuration directory for HTCondor
RUN mkdir -p /etc/condor/config.d
# Add HTCondor configuration files
COPY condor_config /etc/condor/
# Copy configuration files (currently all, to be optimised)
COPY config.d  /etc/condor/config.d/

RUN groupadd -r condor && \
    useradd -r -g condor -d /var/lib/condor -s /sbin/nologin condor

WORKDIR /opt/app
USER $NB_UID
#ENTRYPOINT ["tini", "-g", "/usr/bin/prepare.sh"]
ENTRYPOINT ["tini", "-g", "--"]
