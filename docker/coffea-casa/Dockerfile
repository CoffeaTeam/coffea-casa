FROM coffeateam/coffea-dask:0.7.1-g5e669a7

# Update: 6.01.2021
# https://github.com/jupyter/docker-stacks/blob/master/base-notebook/Dockerfile

LABEL maintainer="Oksana Shadura <ksu.shadura@gmail.com>"
ARG NB_USER="jovyan"
ARG NB_UID="1000"
ARG NB_GID="100"

USER root
# Install all OS dependencies for notebook server that starts but lacks all
# features (e.g., download as all possible file formats)
RUN apt-get update \
     && apt-get install -yq --no-install-recommends \
     procps \
     vim \
     wget \
     sudo \
     locales \
     fonts-liberation \
     && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
        locale-gen

ENV LC_ALL=en_US.UTF-8 \
        LANG=en_US.UTF-8 \
        LANGUAGE=en_US.UTF-8

# Configure environment
ENV CONDA_DIR /opt/conda
ENV SHELL /bin/bash
ENV NB_USER $NB_USER
ENV NB_UID $NB_UID
ENV NB_GID $NB_GID
ENV HOME /home/$NB_USER
ENV PATH "/opt/conda/bin/:$PATH"

# Copy a script that we will use to correct permissions after running certain commands
COPY fix-permissions /usr/local/bin/fix-permissions
RUN chmod a+rx /usr/local/bin/fix-permissions

# Enable prompt color in the skeleton .bashrc before creating the default NB_USER
# hadolint ignore=SC2016
RUN sed -i 's/^#force_color_prompt=yes/force_color_prompt=yes/' /etc/skel/.bashrc && \
   # Add call to conda init script see https://stackoverflow.com/a/58081608/4413446
   echo 'eval "$(command conda shell.bash hook 2> /dev/null)"' >> /etc/skel/.bashrc

# Create NB_USER with name jovyan user with UID=1000 and in the 'users' group
# and make sure these dirs are writable by the `users` group.
RUN echo "auth requisite pam_deny.so" >> /etc/pam.d/su && \
    sed -i.bak -e 's/^%admin/#%admin/' /etc/sudoers && \
    sed -i.bak -e 's/^%sudo/#%sudo/' /etc/sudoers && \
    useradd -m -s /bin/bash -N -u $NB_UID $NB_USER && \
    mkdir -p $CONDA_DIR && \
    chown $NB_USER:$NB_GID $CONDA_DIR && \
    chmod g+w /etc/passwd && \
    fix-permissions $HOME && \
    fix-permissions $CONDA_DIR

USER $NB_UID
WORKDIR $HOME
# Setup work directory for backward-compatibility
RUN mkdir "/home/$NB_USER/work" && \
    fix-permissions "/home/$NB_USER"

# Install Jupyter Notebook, Lab, and Hub
# Generate a notebook server config
# Cleanup temporary files
# Correct permissions
# Do all this in a single RUN command to avoid duplicating all of the
# files across image layers when the permissions change
RUN conda install --quiet --yes \
    -c conda-forge \
    'notebook==6.1.6' \
    'jupyterhub==1.3.0' \
    'jupyterlab==2.2.9' \
    jupyterlab_widgets \
    # Conflicts needs to be resolved before
    #jupyterlab-lsp \
    jupyterlab-git \
    dask_labextension && \
    conda clean --all -f -y && \
    npm cache clean --force && \
    jupyter notebook --generate-config && \
    rm -rf $CONDA_DIR/share/jupyter/lab/staging && \
    rm -rf /home/$NB_USER/.cache/yarn

EXPOSE 8888

# Configure container startup
ENTRYPOINT ["tini", "-g", "--"]

# Copy local files as late as possible to avoid cache busting
COPY start.sh start-notebook.sh start-singleuser.sh /usr/local/bin/
# Currently need to have both jupyter_notebook_config and jupyter_server_config to support classic and lab
COPY jupyter_notebook_config.py /etc/jupyter/

# Fix permissions on /etc/jupyter as root
USER root

# Prepare upgrade to JupyterLab V3.0 #1205
RUN sed -re "s/c.NotebookApp/c.ServerApp/g" \
    /etc/jupyter/jupyter_notebook_config.py > /etc/jupyter/jupyter_server_config.py

# Fix permissions on /etc/jupyter as root
RUN fix-permissions /etc/jupyter/ && \
    fix-permissions "$(dirname $CONDA_DIR)" && \
    fix-permissions "$(dirname $HOME)"

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Update: 6.01.2021
# https://github.com/jupyter/docker-stacks/blob/master/minimal-notebook/Dockerfile

# Install all OS dependencies for fully functional notebook server
RUN apt-get update && apt-get install -yq --no-install-recommends \
    build-essential \
    gdb \
    vim-tiny \
    git \
    inkscape \
    libsm6 \
    libxext-dev \
    libxrender1 \
    lmodern \
    netcat \
    # ---- nbconvert dependencies ----
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-plain-generic \
    # ----
    tzdata \
    unzip \
    nano-tiny \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
USER $NB_UID
# Dask extention (looks like it is not available in the image)
RUN pip install --no-cache-dir \
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
    rm -rf $HOME/.node-gyp

# TBD: Jupyter lab workspace setup
#COPY jupyterlab-workspace.json $HOME/
#RUN jupyter lab workspaces import $HOME/jupyterlab-workspace.json

USER root
# Preparing directories for Dask conf files, patches and job spool directory for HTCondor
RUN mkdir -p $HOME/.config/dask  && \
    mkdir -p /etc/dask  && \
    mkdir -p /var/lib/condor && \
    mkdir -p $HOME/.condor/tokens.d && \
    mkdir -p /etc/condor/config.d  && \
    mkdir -p $HOME/patches
COPY patches/coffea-xrootd.patch $HOME/patches/

RUN apt-get update \
    && apt-get install -y gcc build-essential

USER $NB_UID
RUN conda install --yes --freeze-installed \
    -c conda-forge \
    conda-build \
    # Conflicts needs to be resolved before
    #python-language-server \
    htcondor \
    xgboost \
    pyhf \
    cmake

# Distributed & dask-jobqueue: we need to install patched version of distributed version, it is will be
# preferable to pull proper dask and distributed versions via pip.
# dask-jobqueue.git -> master has required fixes (no need to patch)
RUN pip install --ignore-installed --no-cache-dir \
    git+git://github.com/oshadura/distributed.git@2021.03.1-coffea-casa#egg=distributed \
    git+git://github.com/CoffeaTeam/coffea-casa.git@master#egg=coffea_casa \
    pyyaml

# Servicex (still wrong dependencies)
#RUN pip install --no-cache-dir servicex-clients

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
# Dask setup - > dask.yml
# Coffea_casa - > jobqueue-coffea-casa.yaml
# Labextention setup - >labextension.yml
COPY dask.yaml labextension.yaml /opt/conda/lib/python3.8/site-packages/coffea_casa/jobqueue-coffea-casa.yaml $HOME/.config/dask/
# REMOVE ME AFTER TAG!
#COPY dask.yaml labextension.yaml /opt/conda/lib/python3.8/site-packages/coffea_casa/jobqueue-coffea-casa.yamlj /etc/dask/

# Fix permissions on /etc/jupyter as root
RUN fix-permissions /etc/jupyter/ && \
    fix-permissions "$(dirname $CONDA_DIR)" && \
    fix-permissions "$(dirname $HOME)"

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
ENV LD_LIBRARY_PATH="/opt/conda/lib/:$LD_LIBRARY_PATH"
ENV XRD_PLUGIN="/opt/conda/lib/libXrdClAuthzPlugin.so"
ENV BEARER_TOKEN_FILE="/etc/cmsaf-secrets/xcache_token"
ENV PATH="/opt/conda/bin/:$PATH"
ENV PYTHONPATH="$HOME/.local/lib/python3.8/site-packages:$PYTHONPATH"

# FIXME: we have a wrong path, let's make a link.
# jovyan@jupyter-oksana-2eshadura-40cern-2ech:~$ echo $PATH
# /opt/conda/condabin:/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games
RUN rm -rf /opt/conda/condabin && ln -s /opt/conda/bin /opt/conda/condabin

#FIXME (recheck patch with new release)
RUN patch /opt/conda/lib/python3.8/site-packages/coffea/processor/executor.py < $HOME/patches/coffea-xrootd.patch

ADD prepare-env.sh /usr/local/bin/
RUN chmod ugo+x /usr/local/bin/prepare-env.sh

USER $NB_UID
WORKDIR $HOME
ENTRYPOINT ["tini", "-g", "--", "/usr/local/bin/prepare-env.sh"]

# Extra packages to be installed (apt, pip, conda) and commands to be executed
# Use bash login shell for entrypoint in order
# to automatically source user's .bashrc
CMD ["start-notebook.sh"]
