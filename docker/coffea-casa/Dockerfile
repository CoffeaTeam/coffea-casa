# based on https://github.com/dask/dask-docker/blob/master/base/Dockerfile
FROM continuumio/miniconda3:latest

#RUN apt-get update && apt-get install -y --no-install-recommends apt-utils

#Script that helps to work out missing packages without editing Docker image
COPY prepare.sh /usr/bin/prepare.sh

# EGI CA certificates (can we get them from conda?)
RUN apt-get install gnupg2 -y \
    && wget -q -O - https://dist.eugridpma.info/distribution/igtf/current/GPG-KEY-EUGridPMA-RPM-3 | apt-key add - \
    && echo "deb http://repository.egi.eu/sw/production/cas/1/current egi-igtf core" >> /etc/apt/sources.list \
    && wget -q -O - https://research.cs.wisc.edu/htcondor/ubuntu/HTCondor-Release.gpg.key | apt-key add - \
    && echo "deb http://research.cs.wisc.edu/htcondor/ubuntu/8.8/bionic bionic contrib" >> /etc/apt/sources.list \
    && echo "deb-src http://research.cs.wisc.edu/htcondor/ubuntu/8.8/bionic bionic contrib" >> /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y ca-policy-egi-core

# Dask dependencies
RUN conda install --yes --freeze-installed \
    -c conda-forge \
    bokeh==2.0.0 \
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
    && conda clean -afy

# HTCondor

#RUN apt-get install -y htcondor \
#    && apt-get purge -y gnupg2 \
#    && apt-get autoremove -y \
#    && rm -rf /var/lib/apt/lists/*

#RUN systemctl start condor && \
#    systemctl enable condor

# Coffea (xxhash should be not needed)
RUN /opt/conda/bin/pip install --no-cache-dir \
    xxhash==1.3.0 \
    coffea==0.6.37

RUN mkdir /opt/app

RUN mkdir /var/lib/condor

RUN groupadd -r condor && \
    useradd -r -g condor -d /var/lib/condor -s /sbin/nologin condor

WORKDIR /opt/app

ENTRYPOINT ["tini", "-g", "/usr/bin/prepare.sh"]
