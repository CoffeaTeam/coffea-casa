#!/bin/bash
set -eux

cd arrow/cpp

mkdir -p release
cd release
cmake \
        -DARROW_SKYHOOK=ON \
        -DARROW_PARQUET=ON \
        -DARROW_WITH_SNAPPY=ON \
        -DARROW_WITH_ZLIB=ON \
        -DARROW_WITH_LZ4=ON \
        -DARROW_DATASET=ON \
        -DARROW_PYTHON=ON \
        -DARROW_CSV=ON \
        ..

make -j4 install

cd arrow/python

pip install --upgrade setuptools==57.0.0 wheel
pip install -r requirements-build.txt -r requirements-test.txt

export WORKDIR=${WORKDIR:-$HOME}
export ARROW_HOME=$WORKDIR/dist
export LD_LIBRARY_PATH=$ARROW_HOME/lib
export PYARROW_WITH_DATASET=1
export PYARROW_WITH_PARQUET=1
export PYARROW_WITH_RADOS=1

python setup.py build_ext --inplace --bundle-arrow-cpp bdist_wheel
pip install dist/*.whl
cp -r dist/*.whl /

python -c "import pyarrow"
python -c "import pyarrow.dataset"
python -c "import pyarrow.parquet"
python -c "from pyarrow.dataset import SkyhookFileFormat"
