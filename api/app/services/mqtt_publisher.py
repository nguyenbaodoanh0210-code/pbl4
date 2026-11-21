"""Non-crashing MQTT JSON publisher for actuator and ESP32-CAM commands."""

import json
import logging
import os

import paho.mqtt.client as mqtt


logger = logging.getLogger(__name__)


def mqtt_settings() -> dict:
    return {
        "broker": os.getenv("MQTT_BROKER", "test.mosquitto.org").strip(),
        "port": int(os.getenv("MQTT_PORT", "1883")),
        "username": os.getenv("MQTT_USERNAME") or None,
        "password": os.getenv("MQTT_PASSWORD") or None,
        "tls": os.getenv("MQTT_TLS", "false").lower() == "true",
        "enabled": os.getenv("MQTT_PUBLISH_ENABLED", "true").lower() == "true",
        "timeout": float(os.getenv("MQTT_PUBLISH_TIMEOUT", "2.5")),
    }


def control_topic(greenhouse_id: str) -> str:
    return f"smart_garden/{greenhouse_id}/control"


def camera_cmd_topic(greenhouse_id: str) -> str:
    return f"smart_garden/{greenhouse_id}/camera/cmd"


def create_mqtt_client() -> mqtt.Client:
    callback_api = getattr(mqtt, "CallbackAPIVersion", None)
    if callback_api is not None:
        return mqtt.Client(callback_api.VERSION1)
    return mqtt.Client()


def publish_mqtt_json(topic: str, payload: dict) -> dict:
    """Publish a JSON payload safely; never raises on broker/network failure."""
    cfg = mqtt_settings()
    if not cfg["enabled"] or not cfg["broker"]:
        return {"published": False, "topic": topic, "error": "MQTT publish bị tắt hoặc chưa cấu hình broker"}

    client = create_mqtt_client()
    try:
        if cfg["username"] or cfg["password"]:
            client.username_pw_set(cfg["username"], cfg["password"])
        if cfg["tls"]:
            client.tls_set()
        client.connect(cfg["broker"], cfg["port"], keepalive=15)
        client.loop_start()
        info = client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1)
        info.wait_for_publish(timeout=cfg["timeout"])
        client.loop_stop()
        client.disconnect()
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            return {"published": False, "topic": topic, "error": f"MQTT rc={info.rc}"}
        return {"published": True, "topic": topic, "error": None}
    except Exception as exc:
        logger.warning("MQTT publish skipped/failed for topic=%s (%s)", topic, type(exc).__name__)
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass
        return {"published": False, "topic": topic, "error": type(exc).__name__}
