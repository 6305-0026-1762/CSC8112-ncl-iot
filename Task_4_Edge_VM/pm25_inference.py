import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import matplotlib.pyplot as plt
import paho.mqtt.client as mqtt
import tensorflow as tf

MQTT_BROKER = os.getenv("MQTT_BROKER", "emqx")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "uo/pm25")

TFLITE_MODEL_PATH = os.getenv("TFLITE_MODEL_PATH", "pm25_model.tflite")

LABEL_CLASSES = np.array(["GREEN", "RED", "YELLOW"])
SCALER_MEAN = 8.73966472
SCALER_SCALE = 6.06153744

def standardize_value(value: float) -> float:
    return (value - SCALER_MEAN) / SCALER_SCALE


def load_tflite_model():
    interpreter = tf.lite.Interpreter(model_path=TFLITE_MODEL_PATH)
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    print("Loaded TFLite model:")
    print("  Input:", input_details)
    print("  Output:", output_details)

    return interpreter, input_details, output_details


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"Failed to connect to MQTT broker, reason code: {reason_code}")


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)
    except Exception as e:
        print(f"Failed to parse MQTT message: {e}")
        return

    if isinstance(data, dict) and data.get("Type") == "END":
        print("Received END signal from injector (inference).")
        make_plots_and_summary(userdata)
        client.disconnect()
        return

    ts = data.get("Timestamp")
    value = data.get("Value")
    if ts is None or value is None:
        return

    try:
        value = float(value)
        ts_raw = int(ts)
    except (TypeError, ValueError):
        return

    if ts_raw > 1_000_000_000_000:
        ts_sec = ts_raw / 1000.0
    else:
        ts_sec = ts_raw
    dt = datetime.fromtimestamp(ts_sec, tz=timezone.utc)

    x_scaled = standardize_value(value)

    interpreter = userdata["interpreter"]
    input_details = userdata["input_details"]
    output_details = userdata["output_details"]

    input_index = input_details[0]["index"]
    output_index = output_details[0]["index"]

    input_data = np.array([[x_scaled]], dtype=np.float32)
    interpreter.set_tensor(input_index, input_data)
    interpreter.invoke()
    output_data = interpreter.get_tensor(output_index)

    pred_idx = int(np.argmax(output_data, axis=1)[0])
    pred_label = LABEL_CLASSES[pred_idx]

    print(f"[INFER] {dt.isoformat()}  PM2.5={value:.2f} -> {pred_label}")

    userdata["timestamps"].append(dt)
    userdata["values"].append(value)
    userdata["pred_labels"].append(pred_label)


def make_plots_and_summary(userdata):
    timestamps = userdata["timestamps"]
    values = userdata["values"]
    pred_labels = userdata["pred_labels"]

    if not timestamps:
        print("No inference data collected. No plots will be generated.")
        return

    class_counts = {cls: 0 for cls in LABEL_CLASSES}
    for lbl in pred_labels:
        class_counts[lbl] += 1

    for cls, count in class_counts.items():
        print(f"  {cls}: {count}")

    fig1, ax1 = plt.subplots(figsize=(6, 4))
    labels = list(class_counts.keys())
    counts = [class_counts[l] for l in labels]
    bars = ax1.bar(labels, counts)
    ax1.set_ylabel("Count")
    ax1.set_title("Predicted PM2.5 Quality Distribution")
    ax1.bar_label(bars)
    plt.tight_layout()
    fig1.savefig("predicted_class_counts.png")
    plt.close(fig1)
    print("Saved predicted_class_counts.png")

    fig2, ax2 = plt.subplots(figsize=(10, 5))
    color_map = {
        "GREEN": "green",
        "YELLOW": "gold",
        "RED": "red",
    }

    for dt, val, lbl in zip(timestamps, values, pred_labels):
        ax2.scatter(dt, val, c=color_map.get(lbl, "black"), s=10)

    ax2.set_xlabel("Time")
    ax2.set_ylabel("PM2.5 Value")
    ax2.set_title("PM2.5 over Time with Predicted Quality")
    plt.tight_layout()
    fig2.savefig("pm25_time_series_predictions.png")
    plt.close(fig2)
    print("Saved pm25_time_series_predictions.png")


def main():
    interpreter, input_details, output_details = load_tflite_model()

    userdata = {
        "interpreter": interpreter,
        "input_details": input_details,
        "output_details": output_details,
        "timestamps": [],
        "values": [],
        "pred_labels": [],
    }

    client = mqtt.Client(
        client_id="PM25_Inference",
        userdata=userdata,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    client.on_connect = on_connect
    client.on_message = on_message

    print("Connecting to MQTT broker...")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    except Exception as e:
        print(f"Could not connect to MQTT broker: {e}")
        sys.exit(1)

    print("Waiting for PM2.5 data and END signal for inference...")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("Interrupted, disconnecting...")
        client.disconnect()


if __name__ == "__main__":
    main()

