# based on https://github.com/dask/dask-docker/blob/master/base/Dockerfile
FROM continuumio/miniconda3:latest

#Script that helps to work out missing packages without editing Docker image
COPY prepare.sh /usr/bin/prepare.sh

# EGI CA certificates
RUN apt-get install gnupg2 -y \
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
    xrootd==4.11.2 \
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
RUN if [ -f "/etc/cmsaf-secrets/xcache_token" ]; then BEARER_TOKEN_FILE=$(cat /etc/cmsaf-secrets/xcache_token); fi

RUN groupadd -r condor && \
    useradd -r -g condor -d /var/lib/condor -s /sbin/nologin condor

WORKDIR /opt/app

#ENTRYPOINT ["tini", "-g", "/usr/bin/prepare.sh"]
ENTRYPOINT ["tini", "-g", "--"]
