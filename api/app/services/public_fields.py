"""Public API fields exclude retired fertilizer sensors while preserving historical storage."""
def sensor_fields(row):
    return {name: getattr(row, name) for name in
            ("log_id", "device_id", "timestamp", "temperature", "humidity", "soil_moisture", "light_level")}


def crop_fields(row):
    retired = {"optimum_ph", "target_n", "target_p", "target_k"}
    return {column.key: getattr(row, column.key) for column in row.__table__.columns if column.key not in retired}
