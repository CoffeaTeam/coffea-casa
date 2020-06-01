# based on https://github.com/dask/dask-docker/blob/master/base/Dockerfile
FROM continuumio/miniconda3:latest

# Configure environment
ENV SHELL /bin/bash
ENV NB_USER jovyan
ENV NB_UID 1000
ENV HOME /home/$NB_USER
ENV PATH=$HOME/.local/bin:$PATH

# Create jovyan user with UID=1000 and in the 'users' group
RUN useradd -m -s /bin/bash -N -u $NB_UID $NB_USER

# Fix permissions
RUN chown -R $NB_USER:users $HOME

#Script that helps to work out missing packages without editing Docker image
COPY prepare-extra-packages.sh /usr/bin/prepare-extra-packages.sh

#
RUN mkdir -p /etc/cmsaf-secrets/

#Preparing patches
COPY patches/ $HOME/

# Update repositories
RUN apt-get update

# EGI CA certificates
RUN apt-get install build-essential gnupg2 openssh-client libssl-dev zlib1g-dev uuid-dev -y \
    && wget -q -O - https://dist.eugridpma.info/distribution/igtf/current/GPG-KEY-EUGridPMA-RPM-3 | apt-key add - \
    && echo "deb http://repository.egi.eu/sw/production/cas/1/current egi-igtf core" >> /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y ca-policy-egi-core \
    && apt-get purge -y gnupg2 \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

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
    cmake \
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
    coffea==0.6.39

# We need to build xrootd and xrdcl-authz-plugin from scratch :( - xrootd looks like is not distributed on Ubuntu
RUN cd /tmp && \
    git clone https://github.com/xrootd/xrootd.git && \
    cd xrootd && \
    git checkout v4.12.1 &&\
   # Patch is used for 5.0.0-HEAD (xrootd-pr1199.patch)
    git apply /home/$NB_USER/xrootd-ubuntu.patch && \
    mkdir build && \
    cd  build && \
    cmake /tmp/xrootd -DENABLE_XRDCL=ON -DBUILD_PYTHON=ON -DENABLE_PYTHON=TRUE -DCMAKE_INSTALL_PREFIX=/usr -DPYTHON_EXECUTABLE=/opt/conda/bin/python && \
    make -j4

USER root
RUN cd /tmp/xrootd/build && make install
    ##cd /tmp && \
    ##rm -rf xrootd

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

USER root
# Add job spool directory for HTCondor
RUN mkdir /var/lib/condor && \
    mkdir -p $HOME/.condor/tokens.d && \
    mkdir -p /etc/condor/config.d
# Add HTCondor configuration files
COPY condor_config /etc/condor/
# Copy configuration files (currently all, to be optimised)
COPY config.d  /etc/condor/config.d/

RUN groupadd -r condor && \
    useradd -r -g condor -d /var/lib/condor -s /sbin/nologin condor

# Dask environment
# TBD: should be changed to UNL home dir
RUN mkdir /opt/app
RUN chown -R jovyan:condor /opt/app
#TBD: mount /hadoop?

# Enable iptables
#USER root
# Open 8787 port in firewall
#RUN ufw allow 8787/tcp && \
#    ufw enable

ADD prepare-env.sh /usr/local/bin/
RUN chmod ugo+x /usr/local/bin/prepare-env.sh


# No need to have it here, we hope to land in Condor DIR
#WORKDIR /opt/app
USER $NB_USER

ENTRYPOINT ["tini", "-g", "--", "/usr/local/bin/prepare-env.sh"]
