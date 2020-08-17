# Partially based on https://github.com/dask/dask-docker/blob/master/base/Dockerfile
FROM jupyter/minimal-notebook:latest

# Configure environment
ENV SHELL /bin/bash
ENV NB_USER jovyan
ENV NB_Ua 1000
ENV HOME /home/$NB_USER
ENV PATH=$HOME/.local/bin:$PATH

# Jupyterlab
# Add extra plugins
RUN jupyter labextension install --no-build @jupyter-widgets/jupyterlab-manager && \
    jupyter labextension install --no-build @jupyterlab/git && \
    jupyter labextension install --no-build @jupyterlab/github && \
    jupyter labextension install --no-build dask-labextension

# Dask extention (looks like it is not available in the image)
RUN pip install --no-cache-dir \
  dask_labextension \
  jupyterlab_git \
  jupyterlab_github

# Enable the serverextensions that do not use the conf.d approach and
# build JupyterLab.
RUN jupyter serverextension enable --sys-prefix jupyterlab_git && \
    jupyter lab build --dev-build=False && jupyter lab clean && \
    npm cache clean --force && \
    rm -rf $HOME/.cache/yarn && \
    rm -rf $HOME/.node-gyp && \
    fix-permissions $CONDA_DIR && \
    fix-permissions /home/$NB_USER

# Jupyter lab workspace setup
COPY jupyterlab-workspace.json $HOME/jupyterlab-workspace.json
RUN jupyter lab workspaces import $HOME/jupyterlab-workspace.json

USER root
# Preparing directories for Dask conf files, patches and job spool directory for HTCondor
RUN mkdir -p $HOME/.config/dask  && \
    mkdir -p /etc/dask  && \
    mkdir -p /var/lib/condor && \
    mkdir -p /home/$NB_UID/.condor/tokens.d && \
    mkdir -p /etc/condor/config.d  && \
    mkdir -p $HOME/patches
COPY patches/ $HOME/patches/

# EGI CA certificates
# (as well as xrootd dependencies: libssl-dev zlib1g-dev uuid-dev)
RUN apt-get update \
    && apt-get install -y gnupg2 \
    python-setuptools \
    procps \
    && wget -q -O - https://dist.eugridpma.info/distribution/igtf/current/GPG-KEY-EUGridPMA-RPM-3 | apt-key add - \
    && echo "deb http://repository.egi.eu/sw/production/cas/1/current egi-igtf core" >> /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y ca-policy-egi-core \
    && apt-get purge -y --auto-remove \
    && apt-get purge -y gnupg2 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

USER $NB_UID
# Dask dependencies and HTCondor
# https://anaconda.org/conda-forge/htcondor
RUN conda install --yes --freeze-installed \
    -c conda-forge \
    conda-build \
    # IMPORTANT: Python 3.8 doesn't work with coffea
    # python==3.8 \
    python-blosc \
    setuptools \
    cytoolz \
    lz4 \
    nomkl \
    numpy==1.18.1 \
    pandas==1.0.1 \
    tini==0.18.0 \
    # Coffea-casa extras
    bokeh \
    # IMPORTANT: we need apply a patch for distributed: building it from scratch
    # dask==2.20.0 \ Here we expect that dask will be installed with dependencies later
    # distributed \
    dask-jobqueue \
    xrootd==5.0.1 \
    htcondor \
    # Extra packages
    matplotlib==3.2.1 \
    numba==0.48.0 \
    && conda clean -tipsy \
    && jupyter lab clean \
    && jlpm cache clean \
    && npm cache clean --force \
    && find /opt/conda/ -type f,l -name '*.a' -delete \
    && find /opt/conda/ -type f,l -name '*.pyc' -delete \
    && find /opt/conda/ -type f,l -name '*.js.map' -delete \
    && find /opt/conda/lib/python*/site-packages/bokeh/server/static -type f,l -name '*.js' -not -name '*.min.js' -delete \
    && rm -rf /opt/conda/pkgs \
    && conda build purge-all

# Coffea
RUN pip install --no-cache-dir \
    xxhash==1.3.0 \
    coffea==0.6.42 \
    # Needed for xrootd-authz-plugin compilation
    cmake

# We will need to install a new version
RUN pip uninstall -y dask distributed

# Dask-jobqueue && distributed that needs to be patched (hopefully it will pull dask as well)
# + coffea-casa mini module (still prototype)
# -------Dask-jobqueue -------------------------------
RUN cd /tmp && \
    # ------- coffea-casa -------------------------------
    # (patched distributed will be installed as a part of coffea-casa module setup
    cd /tmp && \
    git clone https://github.com/CoffeaTeam/coffea-casa.git && \
    cd coffea-casa && \
    pip install --no-cache-dir -e .

USER root
# Dask setup - > dask.yml
# Labextention setup - >labextension.yml
COPY dask.yaml labextension.yaml $HOME/.config/dask/
COPY dask.yaml labextension.yaml /etc/dask/

USER $NB_UID
# ------- xrootd-authz-plugin -------------------------------
RUN cd /tmp && \
    # ------- xrdcl-authz-plugin -------------------------------
    git clone https://github.com/bbockelm/xrdcl-authz-plugin.git && \
    cd xrdcl-authz-plugin && \
    mkdir build && \
    cd  build && \
    cmake /tmp/xrdcl-authz-plugin -DCMAKE_INSTALL_PREFIX=/opt/conda && \
    make && \
    make install

USER root
# Add HTCondor configuration files
COPY condor_config /etc/condor/
# Copy configuration files (currently all, to be optimised)
COPY config.d  /etc/condor/config.d/

# Setup HTCondor user/group and change group for user $NB_USER
# Fix error (submitting jobs as user/group 0 (root) is not allowed for security reasons) and
# it configured from kubernetes side and updated in docker container to match it
RUN groupadd -r condor && \
    useradd -r -g condor -d /var/lib/condor -s /sbin/nologin condor  && \
    groupadd 1000 && usermod -g 1000 $NB_USER

# Cleanup
RUN rm -rf /tmp/* \
    && rm -rf $HOME/.cache/.pip/* \
    && find /opt/conda/ -type f,l -name '*.a' -delete \
    && find /opt/conda/ -type f,l -name '*.pyc' -delete \
    && find /opt/conda/ -type f,l -name '*.js.map' -delete \
    && find /opt/conda/lib/python*/site-packages/bokeh/server/static -type f,l -name '*.js' -not -name '*.min.js' -delete \
    && rm -rf /opt/conda/pkgs

# xcache setup
ENV XCACHE_HOST="red-xcache1.unl.edu"
ENV XRD_PLUGINCONFDIR="/opt/conda/etc/xrootd/client.plugins.d/"
ENV LD_LIBRARY_PATH="/opt/conda/lib/"
ENV XRD_PLUGIN="/opt/conda/lib/libXrdClAuthzPlugin.so"
ENV BEARER_TOKEN_FILE="/etc/cmsaf-secrets/xcache_token"

USER $NB_UID
# Use bash login shell for entrypoint in order
# to automatically source user's .bashrc
CMD ["bash", "-l", "-c", "'/usr/local/bin/start-notebook.sh'"]
