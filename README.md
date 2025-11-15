On EDGE VM -

```
docker network create iot-net
docker compose -f docker-compose.edge.yml up --build
```


On CLOUD VM -

```
docker network create iot-net
docker compose -f docker-compose.cloud.yml up --build
```
