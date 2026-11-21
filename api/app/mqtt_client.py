"""Compatibility entrypoint delegating MQTT handling to app.services.mqtt_service."""

from .services.mqtt_service import (
    on_connect,
    on_message,
    process_sensor_payload,
    start_mqtt,
)

__all__ = ["on_connect", "on_message", "process_sensor_payload", "start_mqtt"]


if __name__ == "__main__":
    start_mqtt()
    try:
        input("Press Enter to stop MQTT subscriber\n")
    except KeyboardInterrupt:
        pass
