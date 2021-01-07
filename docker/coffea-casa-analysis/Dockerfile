FROM coffeateam/coffea-dask:latest

# Configure environment
ENV SHELL /bin/bash
ENV NB_USER jovyan
ENV NB_UID 1000
ENV HOME /home/$NB_USER
ENV PATH=$HOME/.local/bin:$PATH

# Create jovyan user with UID=1000 and in the 'users' group
# Fix permissions
RUN useradd -m -s /bin/bash -N -u $NB_UID $NB_USER  && \
    chown -R $NB_USER:users $HOME && \
    mkdir -p /etc/cmsaf-secrets/ && \
    mkdir -p /var/lib/condor && \
    mkdir -p /home/$NB_UID/.condor/tokens.d

RUN apt-get update \
    && apt-get install -y gcc build-essential


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

# Logging@worker
COPY dask.yaml $HOME/.config/dask/

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
