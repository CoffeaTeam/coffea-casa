FROM coffeateam/coffea-dask:0.7.1-g5e669a7

USER root
LABEL maintainer="Oksana Shadura <ksu.shadura@gmail.com>"
ARG NB_USER="jovyan"
ARG NB_UID="1000"
ARG NB_GID="100"

# Hack for GH Actions
ARG GITHUB_ACTIONS="false"

# Configure environment
ENV CONDA_DIR /opt/conda
ENV SHELL /bin/bash
ENV NB_USER $NB_USER
ENV NB_UID $NB_UID
ENV NB_GID $NB_GID
ENV HOME /home/$NB_USER
ENV PATH "/opt/conda/bin/:$PATH"

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
     gcc build-essential \
     && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
        locale-gen
ENV LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8

# Copy a script that we will use to correct permissions after running certain commands
COPY fix-permissions /usr/local/bin/fix-permissions
RUN chmod a+rx /usr/local/bin/fix-permissions

# Create NB_USER with name jovyan user with UID=1000 and in the 'users' group
# and make sure these dirs are writable by the `users` group.
RUN echo "auth requisite pam_deny.so" >> /etc/pam.d/su && \
    sed -i.bak -e 's/^%admin/#%admin/' /etc/sudoers && \
    sed -i.bak -e 's/^%sudo/#%sudo/' /etc/sudoers && \
    useradd -m -s /bin/bash -N -u $NB_UID $NB_USER && \
    mkdir -p $CONDA_DIR && \
    mkdir -p $HOME/.local && \
    mkdir -p /etc/cmsaf-secrets/ && \
    mkdir -p /var/lib/condor && \
    mkdir -p $HOME/patches && \
    mkdir -p $HOME/.condor/tokens.d && \
    chown $NB_USER:$NB_GID $CONDA_DIR && \
    chown $NB_USER:$NB_GID $HOME && \
    chmod g+w /etc/passwd && \
    fix-permissions $HOME && \
    fix-permissions $CONDA_DIR

COPY patches/coffea-xrootd.patch $HOME/patches/

USER $NB_UID
WORKDIR $HOME
# Setup work directory for backward-compatibility
RUN mkdir "/home/$NB_USER/work" && \
    fix-permissions "/home/$NB_USER"

# Dask dependencies and HTCondor
# https://anaconda.org/conda-forge/htcondor
RUN conda install --yes --freeze-installed \
    -c conda-forge \
    htcondor \
    xgboost \
    pyhf \
    cmake \
    && conda clean --all -f -y \
    && conda build purge-all

#
RUN pip install --no-cache-dir \
    # for running/restarting Dask worker in sidecar container
    supervisor
# Since we need to install patched version of distributed version, it is will be
# preferable to pull proper dask and distributed versions via pip.
# dask-jobqueue.git -> master has required fixes (no need to patch)
RUN pip install --ignore-installed --no-cache-dir \
    git+git://github.com/oshadura/distributed.git@2021.03.1-coffea-casa#egg=distributed

# ------- xrootd-authz-plugin -------------------------------
RUN cd /tmp && \
    git clone https://github.com/bbockelm/xrdcl-authz-plugin.git && \
    cd xrdcl-authz-plugin && \
    mkdir build && \
    cd  build && \
    cmake /tmp/xrdcl-authz-plugin -DCMAKE_INSTALL_PREFIX=/opt/conda && \
    make && \
    make install

USER root
# Setup supervisord files
COPY supervisord.conf  /etc/supervisor/
# Fixes https://github.com/CoffeaTeam/jhub/issues/37
#RUN WORKER_ID=$(cat /dev/urandom | tr -dc '0-9' | fold -w 256 | head -n 1 | sed -e 's/^0*//' | head --bytes 5)
#    sed --in-place "s/kubernetes-worker/kubernetes-worker-${WORKER_ID}/g" /etc/supervisor/supervisord.conf

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

# xcache setup (we setup BEARER_TOKEN_FILE later in prepare-env.sh)
ENV XCACHE_HOST="red-xcache1.unl.edu"
ENV XRD_PLUGINCONFDIR="/opt/conda/etc/xrootd/client.plugins.d/"
ENV LD_LIBRARY_PATH="/opt/conda/lib/:$LD_LIBRARY_PATH"
ENV XRD_PLUGIN="/opt/conda/lib/libXrdClAuthzPlugin.so"
ENV BEARER_TOKEN_FILE="/etc/xcache_token"
ENV PATH="/opt/conda/bin/:$PATH"
ENV PYTHONPATH="$HOME/.local/lib/python3.8/site-packages:$PYTHONPATH"

# FIXME: we have a wrong path, let's make a link.
# jovyan@jupyter-oksana-2eshadura-40cern-2ech:~$ echo $PATH
# /opt/conda/condabin:/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games
RUN rm -rf /opt/conda/condabin && ln -s /opt/conda/bin /opt/conda/condabin

#FIXME (recheck patch with new release)
RUN patch /opt/conda/lib/python3.8/site-packages/coffea/processor/executor.py < $HOME/patches/coffea-xrootd.patch

# Cleanup
RUN rm -rf /tmp/* \
    && rm -rf $HOME/.cache/.pip/* \
    && conda clean -tipsy \
    && find /opt/conda/ -type f,l -name '*.a' -delete \
    && find /opt/conda/ -type f,l -name '*.pyc' -delete \
    && find /opt/conda/ -type f,l -name '*.js.map' -delete \
    && find /opt/conda/lib/python*/site-packages/bokeh/server/static -type f,l -name '*.js' -not -name '*.min.js' -delete \
    && conda clean --all -f -y \
    && conda build purge-all

# Prepare HTCondor spec. environment and execute dask-worker command
# If we using this container as a sidecar, we don't setup any HTCondor spec. environment
# nor and execute dask-worker command
ADD prepare-env.sh /usr/local/bin/
RUN chmod ugo+x /usr/local/bin/prepare-env.sh

USER $NB_USER
ENTRYPOINT ["tini", "-g", "--", "/usr/local/bin/prepare-env.sh"]
