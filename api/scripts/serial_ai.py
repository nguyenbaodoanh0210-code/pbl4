"""Inspect ESP32 environmental JSON lines; irrigation runs in the authenticated API."""

import json
import os
import time

import serial



BAUD_RATE = int(os.getenv("ESP32_BAUD_RATE", "115200"))
COM_PORT = os.getenv("ESP32_COM_PORT", "COM6")


def main() -> int:
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
                allowed = ('temperature', 'humidity', 'soil_moisture', 'light_lux')
                print({key:sensor_data.get(key) for key in allowed})
                print('Send readings to /api/ingest/sensors/{device_id} for irrigation control.')
            except (json.JSONDecodeError, ValueError, RuntimeError) as exc:
                print(f"Prediction skipped: {exc}")
    except KeyboardInterrupt:
        print("Stopped serial inference.")
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
