import json
import os
import sys
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import pika

# MQTT (Edge / EMQX)
MQTT_BROKER = os.getenv("MQTT_BROKER", "emqx")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "uo/pm25")

# RabbitMQ (Cloud)
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "pm25_daily_avg")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "student")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "student")


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Preprocessor connected to MQTT broker")
        client.subscribe(MQTT_TOPIC)
        print(f"Subscribed to topic: {MQTT_TOPIC}")
    else:
        print(f"Failed to connect to MQTT broker, reason code: {reason_code}")


def send_to_rabbitmq(daily_avgs):
    """Send one or more daily average records to RabbitMQ."""
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                virtual_host="/",
                credentials=credentials,
            )
        )
    except Exception as e:
        print(f"Could not connect to RabbitMQ: {e}")
        sys.exit(1)

    channel = connection.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)

    for record in daily_avgs:
        body = json.dumps(record)
        print("Sending daily avg to RabbitMQ:", body)
        channel.basic_publish(
            exchange="",
            routing_key=RABBITMQ_QUEUE,
            body=body,
        )

    connection.close()


def finalize_and_send_day(userdata):
    """Finalize current day stats -> print and send to RabbitMQ, then reset."""
    day_ts = userdata.get("current_day_ts")
    count = userdata.get("current_count", 0)
    total = userdata.get("current_sum", 0.0)

    if day_ts is None or count == 0:
        return

    avg = total / count
    record = {"Timestamp": day_ts, "Value": avg}

    # Log nicely
    dt = datetime.fromtimestamp(day_ts, tz=timezone.utc)
    print(f"[DAILY AVG] {dt.date()} -> {avg:.2f}")

    # Send to RabbitMQ
    send_to_rabbitmq([record])

    # Store for summary at the end
    userdata.setdefault("daily_avgs", []).append(record)

    # Reset current-day stats; next message will set a new day_ts
    userdata["current_day_ts"] = None
    userdata["current_sum"] = 0.0
    userdata["current_count"] = 0


def update_daily_stats(userdata, reading):
    """Incrementally update per-day stats for a non-outlier reading."""
    ts = reading.get("Timestamp")
    value = reading.get("Value")
    if ts is None or value is None:
        return

    try:
        ts_raw = int(ts)
        v = float(value)
    except (TypeError, ValueError):
        return

    # Detect ms vs seconds and normalise
    if ts_raw > 1_000_000_000_000:  # heuristic: milliseconds
        ts_sec = ts_raw / 1000.0
    else:
        ts_sec = ts_raw

    dt = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
    day_start = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    day_ts = int(day_start.timestamp())

    current_day_ts = userdata.get("current_day_ts")

    # If we already have a day and this reading is from a new day,
    # finalize the previous one.
    if current_day_ts is not None and day_ts != current_day_ts:
        finalize_and_send_day(userdata)
        current_day_ts = None

    # Start a new day bucket if needed
    if current_day_ts is None:
        userdata["current_day_ts"] = day_ts
        userdata["current_sum"] = 0.0
        userdata["current_count"] = 0

    # Update running stats
    userdata["current_sum"] += v
    userdata["current_count"] += 1


def on_message(client, userdata, msg):
    """Handle incoming PM2.5 readings from MQTT."""
    try:
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)
    except Exception as e:
        print(f"Failed to parse MQTT message: {e}")
        return

    # Handle END control message from injector
    if isinstance(data, dict) and data.get("Type") == "END":
        print("Received END signal from injector")

        # Finalise and send the last day's average
        finalize_and_send_day(userdata)

        # Print summary for the logs
        if userdata.get("daily_avgs"):
            print("Daily averaged PM2.5 data (sent to RabbitMQ):")
            for rec in userdata["daily_avgs"]:
                dt = datetime.fromtimestamp(rec["Timestamp"], tz=timezone.utc)
                print(f"{dt.date()} -> {rec['Value']:.2f}")
        else:
            print("No daily averages computed.")

        # Disconnect so loop_forever() returns and container exits
        client.disconnect()
        return

    # Normal reading path
    userdata["raw"].append(data)

    try:
        value = float(data.get("Value"))
    except (TypeError, ValueError):
        return

    if value > 50:
        print("Received PM2.5 (OUTLIER):", data)
    else:
        print("Received PM2.5 (NORMAL):", data)
        userdata["clean"].append(data)
        # Incremental per-day stats and possibly send a finished day
        update_daily_stats(userdata, data)


def main():
    userdata = {
        "raw": [],
        "clean": [],
        "current_day_ts": None,
        "current_sum": 0.0,
        "current_count": 0,
        "daily_avgs": [],
    }

    client = mqtt.Client(
        client_id="Preprocessor",
        userdata=userdata,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT} ...")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    except Exception as e:
        print(f"Could not connect to MQTT broker: {e}")
        sys.exit(1)

    # Run until we receive the END signal and call client.disconnect()
    print("Waiting for PM2.5 data and END signal from injector...")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("Interrupted, disconnecting...")
        client.disconnect()

    raw_readings = userdata["raw"]
    clean_readings = userdata["clean"]

    print(f"Total readings received: {len(raw_readings)}")
    print(f"Non-outlier readings (<= 50): {len(clean_readings)}")


if __name__ == "__main__":
    main()
