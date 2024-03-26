# Howe to rebuild images with coffea 2024

To rebuild images for 200 gbps challenge, please use Dockerfile.cc-dask-alma8 (image with scheduler) and Dockerfile.cc-analysis-alma8 (worker image): `TAG` should be matching in the both images. 

```
sudo docker build --build-arg TAG="2024.03.26" -t hub.opensciencegrid.org/coffea-casa/cc-dask-alma8:2024.03.26 -f ./Dockerfile.cc-dask-alma8 .

```

```
docker build --build-arg TAG="2024.03.26" -t hub.opensciencegrid.org/coffea-casa/cc-analysis-alma8:2024.03.26 -f ./Dockerfile.cc-analysis-alma8 .
```
