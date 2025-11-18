## Before starting (both cloud and edge) -

```
docker system prune -a

docker container prune
```


## On CLOUD VM -

```
docker network create iot-net
```

```
docker run -d \
  --name rabbitmq \
  --network iot-net \
  -p 5672:5672 \
  -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=student \
  -e RABBITMQ_DEFAULT_PASS=student \
  rabbitmq:3-management
```

### Once the injector is done

```
docker build -t pm25-predictor ./Task_3_Cloud_VM
```
```
docker run \
  --name pm25-predictor \
  --network iot-net \
  -e RABBITMQ_HOST=rabbitmq \
  -e RABBITMQ_PORT=5672 \
  -e RABBITMQ_QUEUE=pm25_daily_avg \
  -e RABBITMQ_USER=student \
  -e RABBITMQ_PASSWORD=student \
  pm25-predictor
```

## On EDGE VM -

```
docker network create iot-net
```

```
docker run -d \
  --name emqx \
  --network iot-net \
  -p 1883:1883 \
  -p 18083:18083 \
  emqx/emqx:5.3
```

```
docker build -t pm25-injector ./Task_1_Edge

docker build -t pm25-preprocessor ./Task_2_Edge_VM

docker build -t pm25-inference ./Task_4_Edge_VM
```

```
docker run \
  --name pm25-preprocessor \
  --network iot-net \
  -e MQTT_BROKER=emqx \
  -e MQTT_PORT=1883 \
  -e MQTT_TOPIC=uo/pm25 \
  -e RABBITMQ_HOST=192.168.0.100 \
  -e RABBITMQ_PORT=5672 \
  -e RABBITMQ_QUEUE=pm25_daily_avg \
  -e RABBITMQ_USER=student \
  -e RABBITMQ_PASSWORD=student \
  pm25-preprocessor
```

```
docker run \
  --name pm25-inference \
  --network iot-net \
  -e MQTT_BROKER=emqx \
  -e MQTT_PORT=1883 \
  -e MQTT_TOPIC=uo/pm25 \
  pm25-inference
```

```
docker run \
  --name pm25-injector \
  --network iot-net \
  -e MQTT_BROKER=emqx \
  -e MQTT_PORT=1883 \
  pm25-injector
```

### Useful commands -

#### To check running (and stopped) containers
```
docker ps -a
```

#### To copy files from container to VM home

##### In EDGE
```
docker cp pm25-inference:/app/pm25_time_series_predictions.png .

docker cp pm25-inference:/app/predicted_class_counts.png .
```

##### In CLOUD
```
docker cp pm25-predictor:/app/pm25_forecast.png .

docker cp pm25-predictor:/app/pm25_daily_avg.png .
```
