FROM coffeateam/coffea-dask:latest

USER root
LABEL maintainer="Oksana Shadura <ksu.shadura@gmail.com>"
ARG NB_USER="jovyan"
ARG NB_UID="1000"
ARG NB_GID="100"

USER root
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

# Install all OS dependencies for notebook server that starts but lacks all
# features (e.g., download as all possible file formats)
RUN apt-get update \
     && apt-get install -yq --no-install-recommends \
     libssl-dev \
     zlib1g-dev \
     uuid-dev  \
     openssh-client \
     python-setuptools \
     procps \
     vim \
     wget \
     sudo \
     locales \
     fonts-liberation \
     && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
        locale-gen

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
    mkdir -p /etc/cmsaf-secrets/ && \
    mkdir -p /var/lib/condor && \
    mkdir -p /home/$NB_UID/.condor/tokens.d && \
    chown $NB_USER:$NB_GID $CONDA_DIR && \
    chmod g+w /etc/passwd && \
    fix-permissions $HOME && \
    fix-permissions $CONDA_DIR

RUN apt-get update \
    && apt-get install -y gcc build-essential

USER $NB_UID
# Dask dependencies and HTCondor
# https://anaconda.org/conda-forge/htcondor
RUN conda install --yes --freeze-installed \
    -c conda-forge \
    htcondor \
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
    git+git://github.com/oshadura/distributed.git@2020.12.0-coffea-casa#egg=distributed \
    dask-jobqueue

# Enabled for debugging purposes (combination of conda xrootd 5.0.3 + xrdcl-authz-plugin is broken)
# ------- xrootd -------------------------------
RUN cd /tmp && \
    git clone https://github.com/xrootd/xrootd.git && \
    cd xrootd && \
    git checkout v5.0.3 && \
    mkdir build && \
    cd  build && \
    cmake /tmp/xrootd -DENABLE_XRDCL=ON -DBUILD_PYTHON=ON -DCMAKE_BUILD_TYPE=Debug -DENABLE_PYTHON=TRUE -DCMAKE_INSTALL_PREFIX=/opt/conda -DPYTHON_EXECUTABLE=/opt/conda/bin/python && \
    make -j4 && \
    make install

# ------- xrootd-authz-plugin -------------------------------
RUN cd /tmp && \
    git clone https://github.com/oshadura/xrdcl-authz-plugin.git && \
    cd xrdcl-authz-plugin && \
    git checkout fix-mem-leak && \
    mkdir build && \
    cd  build && \
    cmake /tmp/xrdcl-authz-plugin -DCMAKE_BUILD_TYPE=Debug -DCMAKE_INSTALL_PREFIX=/opt/conda && \
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
ENV LD_LIBRARY_PATH="/opt/conda/lib/"
ENV XRD_PLUGIN="/opt/conda/lib/libXrdClAuthzPlugin.so"
ENV BEARER_TOKEN_FILE="/etc/xcache_token"

# Cleanup
RUN rm -rf /tmp/* \
    && rm -rf $HOME/.cache/.pip/* \
    && find /opt/conda/ -type f,l -name '*.a' -delete \
    && find /opt/conda/ -type f,l -name '*.pyc' -delete \
    && find /opt/conda/ -type f,l -name '*.js.map' -delete \
    && find /opt/conda/lib/python*/site-packages/bokeh/server/static -type f,l -name '*.js' -not -name '*.min.js' -delete \
    && rm -rf /opt/conda/pkgs

# Prepare HTCondor spec. environment and execute dask-worker command
# If we using this container as a sidecar, we don't setup any HTCondor spec. environment
# nor and execute dask-worker command
ADD prepare-env.sh /usr/local/bin/
RUN chmod ugo+x /usr/local/bin/prepare-env.sh

USER $NB_USER
ENTRYPOINT ["tini", "-g", "--", "/usr/local/bin/prepare-env.sh"]
