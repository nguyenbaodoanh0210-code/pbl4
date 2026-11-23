"""Run exactly one worker: python -m app.irrigation_worker. No implicit startup on web reload."""
import logging
import time
from .core.database import SessionLocal
from .services.mqtt_service import start_mqtt
from .services.actuator_service import enforce_timeouts


def main():
    client = start_mqtt()
    try:
        while True:
            with SessionLocal() as db:
                try:
                    enforce_timeouts(db)
                except Exception as exc:
                    db.rollback()
                    logging.error("Irrigation watchdog failed: %s", type(exc).__name__)
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
