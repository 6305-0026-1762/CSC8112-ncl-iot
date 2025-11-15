import requests
import json
import paho.mqtt.client as mqtt
import time
import sys
import os

DATA_URL = "https://github.com/ncl-iot-team/CSC8112/raw/refs/heads/main/data/uo_data.min.json"

MQTT_BROKER = os.getenv("MQTT_BROKER", "emqx")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "uo/pm25")


def extract_pm25_data(json_data):
    pm25_readings = []
    sensors = json_data.get("sensors", [])

    for sensor in sensors:
        data = sensor.get("data", {})
        if "PM2.5" in data:
            readings = data["PM2.5"]
            for reading in readings:
                payload = {
                    "Timestamp": reading.get("Timestamp"),
                    "Value": reading.get("Value"),
                }
                pm25_readings.append(payload)
    return pm25_readings


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected to MQTT Broker!")
    else:
        print(f"Failed to connect, reason code {reason_code}")


def main():
    # Fetch source data
    try:
        response = requests.get(DATA_URL)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to download data: {e}")
        sys.exit(1)

    json_response = response.json()

    # Debug preview for report
    print("Printing first 500 characters from the raw data stream..")
    preview = json.dumps(json_response, indent=2)[:500]
    print(preview)

    # Extract PM2.5 readings
    pm25_data = extract_pm25_data(json_response)
    print(f"Extracted {len(pm25_data)} PM2.5 readings")

    # MQTT client setup (paho-mqtt v2 API)
    client = mqtt.Client(
        client_id="DataInjector",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    client.on_connect = on_connect

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        print(f"Could not connect to MQTT broker: {e}")
        sys.exit(1)

    client.loop_start()

    # Wait for connection (up to 10 seconds)
    connection_start_time = time.time()
    while (not client.is_connected()) and (time.time() - connection_start_time < 10):
        time.sleep(0.1)

    if not client.is_connected():
        print("Failed to connect to MQTT broker in 10 seconds. Exiting.")
        client.loop_stop()
        sys.exit(1)

    # Publish all PM2.5 readings
    for reading in pm25_data:
        message = json.dumps(reading)
        print("Sending:", message)
        client.publish(MQTT_TOPIC, message)
        time.sleep(0.1)  # small delay just to slow the stream for demo/logs

    # Send END control message so the preprocessor knows we're done
    end_message = json.dumps({"Type": "END"})
    print("Sending END signal:", end_message)
    client.publish(MQTT_TOPIC, end_message)

    print("Finished publishing data.")

    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
