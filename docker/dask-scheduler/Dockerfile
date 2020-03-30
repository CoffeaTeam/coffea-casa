# FROM daskdev/dask:2.9.0

FROM continuumio/miniconda3:4.7.12

RUN apt-get install gnupg2 -y \
    && wget -q -O - https://dist.eugridpma.info/distribution/igtf/current/GPG-KEY-EUGridPMA-RPM-3 | apt-key add - \
    && echo "deb http://repository.egi.eu/sw/production/cas/1/current egi-igtf core" >> /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y ca-policy-egi-core \
    && apt-get purge -y gnupg2 \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

RUN conda install --yes \
    -c conda-forge \
    lz4 \
    xrootd==4.11.0 \
    tini==0.18.0 \
    && conda clean -tipsy

RUN conda install --yes \
   -c conda-forge \
    python-blosc \
    cytoolz \
    bokeh==1.3.4 \
    dask==2.10.1 \
    numpy==1.18.1 \
    pandas==0.25.3 \
    numba==0.48.0 \
    matplotlib==3.1.2 \
    scipy==1.4.1 \
    && conda clean -tipsy

RUN /opt/conda/bin/pip install --no-cache-dir https://github.com/CoffeaTeam/coffea/archive/daskaffinity.zip # dev2

RUN /opt/conda/bin/pip install coffea

RUN /opt/conda/bin/conda install -c anaconda cloudpickle -y

RUN mkdir /opt/app

RUN mkdir /var/lib/condor

RUN groupadd -r condor && \
    useradd -r -g condor -d /var/lib/condor -s /sbin/nologin condor

WORKDIR /opt/app

ENTRYPOINT ["tini", "-g", "--"]
