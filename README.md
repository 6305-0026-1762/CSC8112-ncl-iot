# CSC8112 – IoT Data Pipeline (Tasks 1–3 + Local Task 4)

This repository implements the first parts of the CSC8112 coursework:

- **Task 1** – Data injector (Edge, MQTT → EMQX)
- **Task 2** – Data preprocessing operator (Edge, MQTT → AMQP/RabbitMQ)
- **Task 3** – Time-series prediction & visualisation (Cloud/local, RabbitMQ → Prophet)
- **Task 4 (local)** – PM2.5 quality classifier training + TFLite conversion (no edge component yet)

Everything is wired together with Docker and Docker Compose so it can be run end-to-end locally.

---

## 1. Prerequisites

- Docker
- Docker Compose (v2)
- Internet access (to download images and data from GitHub, and Python packages inside containers)

---

## 2. Project structure

- `Task_1_Edge/`
  - `data_injector.py` – downloads Urban Observatory JSON, extracts PM2.5 readings, publishes to MQTT.
  - `requirements.txt`
  - `Dockerfile` – builds the injector container.

- `Task_2_Edge_VM/`
  - `preprocessor.py` – subscribes to PM2.5 MQTT topic, prints all readings, filters outliers, computes daily averages, sends them to RabbitMQ.
  - `requirements.txt`
  - `Dockerfile`
  - `docker-compose.preprocessor.yml` – Edge-only compose to run the preprocessor against a RabbitMQ instance.

- `Task_2_Cloud_VM/`
  - `docker-compose.rabbitmq.yml` – Cloud-side compose to run `rabbitmq:3-management`.

- `Task_3_Cloud_VM/`
  - `ml_engine.py` – provided Prophet-based ML engine (from `CSC8112_MLEngine`).
  - `predictor.py` – reads daily averages from RabbitMQ, builds a DataFrame, plots historical PM2.5, runs Prophet for 15-day forecast, saves plots.
  - `requirements.txt`
  - `Dockerfile`
  - `docker-compose.predictor.yml` – Cloud-side compose to run the predictor against an existing RabbitMQ instance.

- `docker-compose.local.yml`
  - Local “all-in-one” stack:
    - `emqx` – MQTT broker
    - `injector` – Task 1 data injector
    - `rabbitmq` – Task 2/3 message broker
    - `pm25-preprocessor` – Task 2 preprocessing operator
    - `pm25-predictor` – Task 3 prediction operator

- (Local Task 4 training script lives outside this structure for now; see Task 4 section below.)

---

## 3. Running everything locally (Tasks 1–3)

### 3.1 Create the Docker network

All services share a common external network:

```bash
docker network create iot-net
````

(If it already exists, Docker will complain once; that’s fine.)

### 3.2 Build and run the full pipeline

From the repo root:

```bash
docker compose -f docker-compose.local.yml up --build
```

This will:

1. Start **EMQX** (`emqx`) on `mqtt://localhost:1883`.
2. Start **RabbitMQ** (`rabbitmq`) on:

   * AMQP: `localhost:5672`
   * Management UI: `http://localhost:15672` (user: `student`, pass: `student`)
3. Run **Task 1 injector** (`injector`):

   * Downloads Urban Observatory data.
   * Prints a preview of the raw JSON.
   * Extracts `{ "Timestamp": ..., "Value": ... }` for PM2.5.
   * Publishes all readings to topic `uo/pm25` on EMQX.
   * Sends a final `{"Type": "END"}` control message.
4. Run **Task 2 preprocessor** (`pm25-preprocessor`):

   * Subscribes to `uo/pm25` on EMQX.
   * Prints every PM2.5 reading to the console.
   * Marks outliers (`Value > 50`) explicitly.
   * Maintains per-day stats and prints `[DAILY AVG] YYYY-MM-DD -> value`.
   * Sends each daily average to RabbitMQ queue `pm25_daily_avg`.
   * Stops cleanly when it sees the `END` control message.
5. Run **Task 3 predictor** (`pm25-predictor`):

   * Connects to RabbitMQ and reads all messages from `pm25_daily_avg`.
   * Prints the raw JSON records.
   * Converts timestamps to `YYYY-MM-DD 00:00:00` and prints `timestamp -> value`.
   * Plots historical daily averages and saves `pm25_daily_avg.png`.
   * Uses the provided `MLPredictor` (Prophet) to train on the daily averages.
   * Predicts the next 15 days of PM2.5 and prints the first few forecast values.
   * Plots the forecast and saves `pm25_forecast.png`.
   * Exits with code 0 when done.

You’ll see all logs in the terminal. For the report, you can capture:

* Injector logs (raw preview, `Sending: {...}`, `Sending END signal`).
* Preprocessor logs (NORMAL / OUTLIER lines, `[DAILY AVG]` lines, RabbitMQ sends).
* Predictor logs (raw JSON, formatted timestamps, forecast head, plot saves).

### 3.3 Running services step-by-step (optional)

If you prefer to run things in stages (useful for debugging / screenshots):

```bash
# 1) Bring up brokers
docker compose -f docker-compose.local.yml up -d emqx rabbitmq

# 2) Run injector + preprocessor once
docker compose -f docker-compose.local.yml up injector pm25-preprocessor

# 3) Run predictor once (reads from RabbitMQ and exits)
docker compose -f docker-compose.local.yml up --build pm25-predictor
```

You can inspect queue contents / message flow with the RabbitMQ UI at `http://localhost:15672` (student / student).

---

## 4. Running components individually (for Azure later)

### Task 1 – Data injector (Edge)

On the Edge VM:

1. Copy `Task_1_Edge/` to the VM.

2. Build the injector image:

   ```bash
   cd Task_1_Edge
   docker build -t pm25-injector .
   ```

3. Start EMQX (either via CLI or your own compose).

4. Run the injector container on the same network as EMQX:

   ```bash
   docker run --rm --network iot-net \
     -e MQTT_BROKER=emqx \
     -e MQTT_PORT=1883 \
     pm25-injector
   ```

### Task 2 – Preprocessor (Edge) and RabbitMQ (Cloud)

* On **Cloud VM**:

  * Use `Task_2_Cloud_VM/docker-compose.rabbitmq.yml` to start RabbitMQ:

    ```bash
    docker compose -f docker-compose.rabbitmq.yml up -d
    ```

* On **Edge VM**:

  * Use `Task_2_Edge_VM/docker-compose.preprocessor.yml`, but set `RABBITMQ_HOST` to the Cloud VM IP instead of `rabbitmq`.
  * Ensure EMQX and the injector are also running on the Edge VM.

### Task 3 – Predictor (Cloud)

On the Cloud VM:

1. Copy `Task_3_Cloud_VM/` and ensure RabbitMQ is running.
2. Build and run the predictor:

   ```bash
   cd Task_3_Cloud_VM
   docker compose -f docker-compose.predictor.yml up --build
   ```

Make sure the Edge preprocessor has already sent daily averages into the `pm25_daily_avg` queue.

---

## 5. Task 4 – Local classifier training (current status)

Task 4 local training is implemented in a separate Python script (not yet containerised):

* Reads a labelled CSV (`PM2.5_labelled_data.csv` or directly from its URL).
* Uses `Value` as the predictor and `Quality` (Green/Yellow/Red) as the label.
* Encodes labels with `LabelEncoder`.
* Splits into train/test (stratified).
* Scales inputs with `StandardScaler`.
* Applies `SMOTE` oversampling to balance classes.
* Trains a small Keras model.
* Evaluates on the test set and prints:

  * Accuracy
  * Classification report
  * Confusion matrix (also saved as `confusion_matrix.png`)
* Converts the model to quantized TFLite (`pm25_model.tflite`) and compares file sizes with a Keras model (`pm25_model.keras`), saving a size comparison plot as `model_size_comparision.png`.

The **edge inference component** for Task 4 (loading `pm25_model.tflite` and running inference on live MQTT PM2.5 readings) will be added later, reusing the MQTT pattern from Task 2.

---

## 6. Notes for the report

When writing the report, you can reference:

* **Task 1**:

  * `Task_1_Edge/data_injector.py`
  * `Task_1_Edge/Dockerfile`
  * EMQX container + logs showing published PM2.5 readings.

* **Task 2**:

  * `Task_2_Edge_VM/preprocessor.py` and its Dockerfile/compose.
  * Logs showing NORMAL / OUTLIER readings, daily averages, and RabbitMQ messages.

* **Task 3**:

  * `Task_3_Cloud_VM/predictor.py` + `ml_engine.py`.
  * The saved plots:

    * `pm25_daily_avg.png` – historical daily averages.
    * `pm25_forecast.png` – Prophet forecast for 15 days.

* **Task 4 (local)**:

  * Training script and its confusion matrix + model size comparison plots.

This README focuses on **running and wiring** the system; the detailed analysis (design choices, parameter settings, performance discussion) will live in the coursework report.

