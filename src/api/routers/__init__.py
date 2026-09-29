from src.api.routers.analytics import router as analytics_router
from src.api.routers.auth import router as auth_router
from src.api.routers.dlq import router as dlq_router
from src.api.routers.health import router as health_router
from src.api.routers.projects import router as projects_router
from src.api.routers.queues import router as queues_router
from src.api.routers.schedules import router as schedules_router
from src.api.routers.tasks import router as tasks_router
from src.api.routers.workers import router as workers_router
from src.api.routers.ws import router as ws_router

__all__ = [
    "analytics_router",
    "auth_router",
    "dlq_router",
    "health_router",
    "projects_router",
    "queues_router",
    "schedules_router",
    "tasks_router",
    "workers_router",
    "ws_router",
]
