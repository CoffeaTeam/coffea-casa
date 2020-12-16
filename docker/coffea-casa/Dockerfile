# Partially based on https://github.com/dask/dask-docker/blob/master/base/Dockerfile
FROM jupyter/minimal-notebook:latest

# Configure environment
ENV SHELL /bin/bash
ENV NB_USER jovyan
ENV NB_UID 1000
ENV HOME /home/$NB_USER
ENV PATH=$HOME/.local/bin:$PATH

# Jupyterlab
# Add extra plugins
#RUN jupyter labextension install --no-build @jupyter-widgets/jupyterlab-manager@2 && \
#    jupyter labextension install --no-build @jupyterlab/git && \
#    jupyter labextension install --no-build @jupyterlab/github && \
#    jupyter labextension install --no-build dask-labextension

# Dask extention (looks like it is not available in the image)
RUN pip install --no-cache-dir \
  jupyterlab_widgets \
  dask_labextension \
  jupyterlab_git \
  jupyterlab_github

# Enable the serverextensions that do not use the conf.d approach and
# build JupyterLab.
RUN jupyter labextension install @jupyter-widgets/jupyterlab-manager && \
    jupyter serverextension enable --sys-prefix jupyterlab_git && \
    jupyter serverextension enable --sys-prefix jupyterlab_github && \
    jupyter labextension install dask-labextension && \
    jupyter serverextension enable dask_labextension && \
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

RUN apt-get update \
    && apt-get install -y gcc build-essential

USER $NB_UID
# Dask dependencies and HTCondor
# https://anaconda.org/conda-forge/htcondor
RUN conda install --yes --freeze-installed \
    -c conda-forge \
    conda-build \
    python==3.8.6 \
    voms \
    ca-policy-lcg \
    python-blosc \
    setuptools \
    cytoolz \
    dask \
    nomkl \
    tini==0.18.0 \
    scipy==1.5.3 \
    bokeh \
    cloudpickle \
    xrootd==5.0.3 \
    htcondor \
    coffea==0.6.44 \
    cmake

#
RUN pip install --no-cache-dir \
    # Servicex
    servicex-clients
# Since we need to install patched version of distributed version, it is will be
# preferable to pull proper dask and distributed versions via pip.
# dask-jobqueue.git -> master has required fixes (no need to patch)
RUN pip install --ignore-installed --no-cache-dir \
    git+git://github.com/oshadura/distributed.git@2020.12.0-coffea-casa#egg=distributed \
    dask-jobqueue \
    git+git://github.com/CoffeaTeam/coffea-casa.git@master#egg=coffea_casa

USER root
# Dask setup - > dask.yml
# Labextention setup - >labextension.yml
COPY dask.yaml labextension.yaml jobqueue-coffea-casa.yaml $HOME/.config/dask/
COPY dask.yaml labextension.yaml jobqueue-coffea-casa.yaml /etc/dask/

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
# Make a symbolic link between installation /opt/conda/etc/grid-security and actual directory /etc/grid-security
RUN ln -s /opt/conda/etc/grid-security /etc/grid-security

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
    && conda clean -tipsy \
    && jupyter lab clean \
    && jlpm cache clean \
    && npm cache clean --force \
    && find /opt/conda/ -type f,l -name '*.a' -delete \
    && find /opt/conda/ -type f,l -name '*.pyc' -delete \
    && find /opt/conda/ -type f,l -name '*.js.map' -delete \
    && conda clean --all -f -y \
    && conda build purge-all

# xcache setup
ENV XCACHE_HOST="red-xcache1.unl.edu"
ENV XRD_PLUGINCONFDIR="/opt/conda/etc/xrootd/client.plugins.d/"
ENV LD_LIBRARY_PATH="/opt/conda/lib/"
ENV XRD_PLUGIN="/opt/conda/lib/libXrdClAuthzPlugin.so"
ENV BEARER_TOKEN_FILE="/etc/cmsaf-secrets/xcache_token"

ADD prepare-env.sh /usr/local/bin/
RUN chmod ugo+x /usr/local/bin/prepare-env.sh

USER $NB_UID
# Extra packages to be installed (apt, pip, conda) and commands to be executed
# Use bash login shell for entrypoint in order
# to automatically source user's .bashrc
CMD ["bash", "-l", "-c", "'/usr/local/bin/prepare-env.sh && /usr/local/bin/start-notebook.sh'"]
