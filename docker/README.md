
Coffea-casa Dask Scheduler:
```
docker build -t coffeateam/coffea-casa:latest coffea-casa
```

```
docker run -it --rm coffeateam/coffea-casa:latest /bin/bash
```

Coffea-casa Dask Worker (HTCondor):
```
docker build -t coffeateam/coffea-casa-analysis:latest coffea-casa-analysis
```

```
docker run -it --rm coffeateam/coffea-casa-analysis:latest /bin/bash
```
