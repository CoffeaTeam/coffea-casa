FROM coffeateam/coffea-dask:0.7.8-fastjet-3.3.4.0rc9-g7921522

# https://github.com/jupyter/docker-stacks/blob/master/base-notebook/Dockerfile

# Fix DL4006
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

USER root
LABEL maintainer="Oksana Shadura <ksu.shadura@gmail.com>"
# Jupyterhub
ARG NB_USER="cms-jovyan"
# Needed for ServiceX cache directory location
ARG USER="cms-jovyan"
ARG NB_UID="6440"
ARG NB_GID="11265"
# Tag
ARG TAG="2021.10.28"
# Secrets
ARG CERT_DIR="/etc/cmsaf-secrets"
ARG BEARER_TOKEN_FILE=$CERT_DIR"/xcache_token"
# Configure Labextention Dask Cluster factory
ARG DASK_ROOT_CONFIG="/opt/dask"
ARG LABEXTENTION_CLUSTER="UNL HTCondor Cluster"
ARG LABEXTENTION_FACTORY_CLASS="CoffeaCasaCluster"
ARG LABEXTENTION_FACTORY_MODULE="coffea_casa"
# XCACHE
ARG XCACHE_HOST="red-xcache1.unl.edu"
# XCACHE settings for Servicex
ARG CACHE_PREFIX="red-xcache1.unl.edu"
ARG SERVICEX_TOKEN=$CERT_DIR"/.servicex"
# Condor settings
ARG CONDOR_HOST="red-condor.unl.edu"
ARG COLLECTOR_NAME="Nebraska T2"
ARG UID_DOMAIN="unl.edu"
ARG SCHEDD_HOST="t3.unl.edu"

# Hack for GH Actions
ARG GITHUB_ACTIONS="false"

# Configure environment
ENV CONDA_DIR /opt/conda
ENV SHELL /bin/bash
ENV NB_USER $NB_USER
ARG USER $NB_USER
ENV USER $USER
ENV NB_UID $NB_UID
ENV NB_GID $NB_GID
ENV HOME /home/$NB_USER
ENV PATH "/opt/conda/bin/:$PATH"
ENV TAG $TAG
ENV CERT_DIR $CERT_DIR
ENV BEARER_TOKEN_FILE $BEARER_TOKEN_FILE
ENV DASK_ROOT_CONFIG $DASK_ROOT_CONFIG
ENV LABEXTENTION_CLUSTER $LABEXTENTION_CLUSTER
ENV LABEXTENTION_FACTORY_CLASS $LABEXTENTION_FACTORY_CLASS
ENV LABEXTENTION_FACTORY_MODULE $LABEXTENTION_FACTORY_MODULE
ENV XCACHE_HOST $XCACHE_HOST
ENV CACHE_PREFIX $CACHE_PREFIX
ENV SERVICEX_TOKEN $SERVICEX_TOKEN
ENV CONDOR_HOST $CONDOR_HOST
ENV COLLECTOR_NAME $COLLECTOR_NAME
ENV UID_DOMAIN $UID_DOMAIN
ENV SCHEDD_HOST $SCHEDD_HOST
     
# Install all OS dependencies for notebook server that starts but lacks all
# features (e.g., download as all possible file formats)
RUN apt-get update --yes && \
    apt-get install --yes --no-install-recommends \
    tini \
    wget \
    ca-certificates \
    sudo \
    locales \
    fonts-liberation \
    procps \
    vim \
    net-tools \
    gdb \
    gcc build-essential && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen

ENV LC_ALL=en_US.UTF-8 \
        LANG=en_US.UTF-8 \
        LANGUAGE=en_US.UTF-8

# Copy a script that we will use to correct permissions after running certain commands
COPY fix-permissions /usr/local/bin/fix-permissions
RUN chmod a+rx /usr/local/bin/fix-permissions

# Enable prompt color in the skeleton .bashrc before creating the default NB_USER
# hadolint ignore=SC2016
RUN sed -i 's/^#force_color_prompt=yes/force_color_prompt=yes/' /etc/skel/.bashrc && \
   # Add call to conda init script see https://stackoverflow.com/a/58081608/4413446
   echo 'eval "$(command conda shell.bash hook 2> /dev/null)"' >> /etc/skel/.bashrc

# Create NB_USER with name cms-jovyan user with given UID and in the 'users' group
# and make sure these dirs are writable by the `users` group.
RUN echo "auth requisite pam_deny.so" >> /etc/pam.d/su && \
    sed -i.bak -e 's/^%admin/#%admin/' /etc/sudoers && \
    sed -i.bak -e 's/^%sudo/#%sudo/' /etc/sudoers && \
    useradd -l -m -s /bin/bash -N -u "${NB_UID}" "${NB_USER}" && \
    mkdir -p "${CONDA_DIR}" && \
    chown -R "${NB_USER}:${NB_GID}" "${CONDA_DIR}" && \
    chown -R "${NB_USER}:${NB_GID}" "${HOME}" && \
    chmod g+w /etc/passwd && \
    fix-permissions "${HOME}" && \
    fix-permissions "${CONDA_DIR}"

USER $NB_USER
WORKDIR $HOME
# Setup work directory for backward-compatibility
RUN mkdir "/home/${NB_USER}/work" && \
    fix-permissions "/home/${NB_USER}"

# Install Jupyter Notebook, Lab, and Hub
# Generate a notebook server config
# Cleanup temporary files
# Correct permissions
# Do all this in a single RUN command to avoid duplicating all of the
# files across image layers when the permissions change
RUN conda install mamba -n base -c conda-forge --yes
RUN mamba install --quiet --yes \
    -c conda-forge \
    'notebook' \
    'jupyterhub' \
    'jupyterlab' \
    jupyterlab_widgets \
    jupyterlab-git \
    dask_labextension && \
    mamba clean -tipsy && \
    npm cache clean --force && \
    jupyter notebook --generate-config && \
    jupyter lab clean && \
    rm -rf "/home/${NB_USER}/.cache/yarn"
    #fix-permissions "${CONDA_DIR}" && \
    #fix-permissions "/home/${NB_USER}"

EXPOSE 8888

# Copy local files as late as possible to avoid cache busting
COPY start.sh start-notebook.sh start-singleuser.sh /usr/local/bin/
# Currently need to have both jupyter_notebook_config and jupyter_server_config to support classic and lab
COPY jupyter_notebook_config.py /etc/jupyter/

# Fix permissions on /etc/jupyter as root
USER root

# Prepare upgrade to JupyterLab V3.0 #1205
RUN sed -re "s/c.NotebookApp/c.ServerApp/g" \
    /etc/jupyter/jupyter_notebook_config.py > /etc/jupyter/jupyter_server_config.py && \
    fix-permissions /etc/jupyter/

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Update: 7.06.2021
# https://github.com/jupyter/docker-stacks/blob/master/minimal-notebook/Dockerfile

# Install all OS dependencies for fully functional notebook server
RUN apt-get update --yes && \
    apt-get install --yes --no-install-recommends \
    vim-tiny \
    git \
    inkscape \
    libsm6 \
    libxext-dev \
    libxrender1 \
    lmodern \
    netcat \
    openssh-client \
    # ---- nbconvert dependencies ----
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-plain-generic \
    # ----
    tzdata \
    unzip \
    gdb \
    nano-tiny && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Create alternative for nano -> nano-tiny
RUN update-alternatives --install /usr/bin/nano nano /bin/nano-tiny 10

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
RUN pip install --upgrade --no-cache-dir \
  jupyterlab_github \
  jupyter_client \
  ipywidgets

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
    rm -rf $HOME/.node-gyp

# FIXME: Jupyter lab workspace setup
#COPY jupyterlab-workspace.json $HOME/
#RUN jupyter lab workspaces import $HOME/jupyterlab-workspace.json

USER root
# Preparing directories for Dask conf files, patches and job spool directory for HTCondor
RUN mkdir -p ${DASK_ROOT_CONFIG}  && chown -R "${NB_USER}:${NB_GID}" ${DASK_ROOT_CONFIG} && \
    mkdir -p /opt/condor/config.d  && chown -R "${NB_USER}:${NB_GID}" /opt/condor/config.d && \
    mkdir -p ${HOME}/.condor/tokens.d && \
    mkdir -p /var/lib/condor && \
    mkdir -p /etc/condor/config.d

USER $NB_UID
RUN mamba install --yes \
    -c conda-forge \
    conda-build \
    htcondor \
    xgboost \
    pyhf \
    vector \
    hist \
    mplhep \
    iminuit \
    cmake

RUN pip install --no-cache-dir coffea[servicex] \
    correctionlib \
    cabinetry \
    func_adl_uproot \
    servicex-databinder \
    pyyaml \
    coffea_casa

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

USER ${NB_UID}
# FIXME: too many files and a lot of hacks! (oshadura)
# Dask setup - > dask.yml
# Coffea_casa - > jobqueue-coffea-casa.yaml
# Labextention setup - >labextension.yml
COPY dask.yaml labextension.yaml jobqueue-coffea-casa.yaml ${DASK_ROOT_CONFIG}/
# Copy HTCondor configuration files (see prepare-env.yaml)
COPY config.d  /opt/condor/config.d/

USER root
# FIXME: too many files and a lot of UNL hacks! (oshadura)
# Add HTCondor configuration files
COPY condor_config /etc/condor/
COPY config.d  /etc/condor/config.d/

# Setup HTCondor user/group and change group for user $NB_USER
# Fix error (submitting jobs as user/group 0 (root) is not allowed for security reasons) and
# it configured from kubernetes side and updated in docker container to match it
RUN groupadd -r condor && \
    useradd -r -g condor -d /var/lib/condor -s /sbin/nologin condor

# FIXME: xrootd/xrd-authz-plugin hack! (oshadura)
# Patching uproot (broken xrootd-authz-plugin with xrootd > 5.2.0 and uproot.MultithreadedXRootDSource)
COPY uproot_xrd_source.patch /opt/conda/lib/python3.8/site-packages/uproot
RUN cd /opt/conda/lib/python3.8/site-packages/uproot && patch < uproot_xrd_source.patch

# FIXME: merge PRs open in distributed.git (oshadura)
# Distributed: we need to install patched version of distributed version
COPY distributed /opt/conda/lib/python3.8/site-packages/distributed
RUN cd /opt/conda/lib/python3.8/site-packages/distributed && \
    patch -p2 < 0001-Patch-from-bbockelman-adaptive-scaling.patch && \
    patch -p2 < 0002-Allow-scheduler-to-preserve-worker-hostnames.patch && \
    patch -p2 < 0003-Activate-patch.patch && \
    patch -p2 < 0004-Add-possibility-to-setup-external_adress-for-schedul.patch
    # && patch -p2 < 0005-Add-patch-from-John-Thiltges.patch

# Cleanup
RUN rm -rf /tmp/* \
    && rm -rf $HOME/.cache/.pip/* \
    && mamba clean -tipsy \
    && jupyter lab clean \
    && jlpm cache clean \
    && npm cache clean --force \
    && find /opt/conda/ -type f,l -name '*.a' -delete \
    && find /opt/conda/ -type f,l -name '*.pyc' -delete \
    && find /opt/conda/ -type f,l -name '*.js.map' -delete \
    && (find /opt/conda/lib/python*/site-packages/bokeh/server/static -type f,l -name '*.js' -not -name '*.min.js' -delete || echo "no bokeh static files to cleanup") \
    && rm -rf /opt/conda/pkgs

# Fix permissions for Dask files
RUN chown -R "${NB_USER}:${NB_GID}" ${DASK_ROOT_CONFIG}/*.yaml
# xcache setup
ENV XRD_PLUGINCONFDIR="/opt/conda/etc/xrootd/client.plugins.d/"
ENV LD_LIBRARY_PATH="/opt/conda/lib/:$LD_LIBRARY_PATH"
ENV XRD_PLUGIN="/opt/conda/lib/libXrdClAuthzPlugin.so"
ENV PATH="/opt/conda/bin/:$PATH"

# FIXME: we have a wrong path, let's make a link.
# cms-jovyan@jupyter-oksana-2eshadura-40cern-2ech:~$ echo $PATH
# /opt/conda/condabin:/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games
RUN rm -rf /opt/conda/condabin && ln -s /opt/conda/bin /opt/conda/condabin

ADD prepare-env.sh /usr/local/bin/
RUN chmod ugo+x /usr/local/bin/prepare-env.sh

# Copy local files as late as possible to avoid cache busting
COPY start.sh start-notebook.sh start-singleuser.sh /usr/local/bin/

# Switch back to cms-jovyan to avoid accidental container runs as root
USER ${NB_UID}
WORKDIR $HOME
#ENTRYPOINT ["tini", "-g", "--"]
ENTRYPOINT ["tini", "-g", "--", "/usr/local/bin/prepare-env.sh"]

# Extra packages to be installed (apt, pip, conda) and commands to be executed
# Use bash login shell for entrypoint in order
# to automatically source user's .bashrc
CMD ["start-notebook.sh"]
