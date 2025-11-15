import json
import os
import sys

import pika
import pandas as pd
import matplotlib.pyplot as plt

from ml_engine import MLPredictor

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "pm25_daily_avg")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "student")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "student")


def collect_daily_averages():
    print("Connecting to RabbitMQ...")
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

    records = []

    print("Collecting messages from RabbitMQ...")
    while True:
        method_frame, properties, body = channel.basic_get(
            queue=RABBITMQ_QUEUE, auto_ack=True
        )
        if method_frame is None:
            # no more messages in queue
            break

        try:
            msg = json.loads(body.decode("utf-8"))
        except Exception as e:
            print(f"Failed to decode message: {e}")
            continue

        records.append(msg)

    connection.close()

    if not records:
        print("No messages found in queue. Exiting.")
        sys.exit(0)

    print("Raw averaged daily PM2.5 data:")
    for r in records:
        print(r)

    return records


def build_dataframe(records):
    df = pd.DataFrame(records)

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="s", utc=True)
    df["Timestamp"] = df["Timestamp"].dt.tz_localize(None)

    print("Averaged daily PM2.5 data:")
    for _, row in df.iterrows():
        ts_str = row["Timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        print(f"{ts_str} -> {row['Value']:.2f}")
    return df

def plot_daily_averages(df):
    output_path="pm25_daily_avg.png"
    plt.figure(figsize=(10, 5))
    plt.plot(df["Timestamp"], df["Value"], marker="o")
    plt.xlabel("Date")
    plt.ylabel("PM2.5 (daily average)")
    plt.title("Daily Average PM2.5")
    plt.grid(True)
    plt.tight_layout()

    print(f"Saving daily averages plot to {output_path}")
    plt.savefig(output_path)
    plt.close()


def run_ml_prediction(df):
    forecast_output_path="pm25_forecast.png"
    pm25_df = df.copy()
    predictor = MLPredictor(pm25_df)
    predictor.train()
    forecast = predictor.predict()

    print("Forecast head:")
    print(forecast[["ds", "yhat"]].head())

    print(f"Plotting forecast and saving to {forecast_output_path} ...")
    fig = predictor.plot_result(forecast)
    fig.savefig(forecast_output_path)


def main():
    records = collect_daily_averages()
    df = build_dataframe(records)
    plot_daily_averages(df)
    run_ml_prediction(df)
    print("Task 3 ML pipeline complete.")


if __name__ == "__main__":
    main()