from .actuator_controller import router as actuator_router
from .ai_controller import router as ai_router
from .alert_controller import router as alert_router
from .auth_controller import router as auth_router
from .camera_controller import router as camera_router
from .device_controller import router as device_router
from .garden_controller import router as garden_router

ALL_ROUTERS = (
    auth_router,
    garden_router,
    device_router,
    actuator_router,
    camera_router,
    ai_router,
    alert_router,
)

__all__ = [
    "ALL_ROUTERS",
    "actuator_router",
    "ai_router",
    "alert_router",
    "auth_router",
    "camera_router",
    "device_router",
    "garden_router",
]
