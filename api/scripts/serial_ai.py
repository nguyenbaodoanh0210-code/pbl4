"""Read ESP32 JSON lines over Serial and run the greenhouse demo model."""

import json
import os
import time

import serial

from app.ai.greenhouse import MODEL_PATH, load_ai_model, predict_greenhouse


BAUD_RATE = int(os.getenv("ESP32_BAUD_RATE", "115200"))
COM_PORT = os.getenv("ESP32_COM_PORT", "COM6")


def main() -> int:
    model_bundle = load_ai_model(MODEL_PATH)
    if model_bundle is None:
        return 1

    try:
        connection = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        print(f"Connected to {COM_PORT} at {BAUD_RATE} baud.")
    except serial.SerialException:
        print(f"Could not open serial port {COM_PORT}; close any other serial monitor.")
        return 1

    try:
        print("Waiting for ESP32 JSON_DATA lines. Press Ctrl+C to stop.")
        while True:
            if connection.in_waiting == 0:
                time.sleep(0.05)
                continue

            raw_line = connection.readline().decode("utf-8", errors="ignore").strip()
            if not raw_line.startswith("JSON_DATA:"):
                continue

            try:
                sensor_data = json.loads(raw_line.removeprefix("JSON_DATA:").strip())
                prediction = predict_greenhouse(sensor_data, model_bundle)
                print(
                    f"Diagnosis={prediction['condition_diagnosis']} "
                    f"Action={prediction['fertilizer_action']}"
                )
                print("Experimental output from the demo dataset; not verified agronomy advice.")
            except (json.JSONDecodeError, ValueError, RuntimeError) as exc:
                print(f"Prediction skipped: {exc}")
    except KeyboardInterrupt:
        print("Stopped serial inference.")
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
