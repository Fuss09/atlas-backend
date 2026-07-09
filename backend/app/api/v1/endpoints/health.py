"""
Atlas - Health Endpoints
========================
GET /health  → liveness  (l'application répond)
GET /ready   → readiness (toutes les dépendances sont connectées)

Ces endpoints sont utilisés par Docker, load balancers, et le monitoring.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.logging import get_logger

router = APIRouter(tags=["Health"])
logger = get_logger(__name__)

_start_time = datetime.now(UTC)


@router.get(
    "/health",
    summary="Liveness check",
    description="Vérifie que l'application est démarrée et répond.",
)
async def health() -> dict[str, Any]:
    """
    Liveness check.
    Répond toujours 200 si l'application est démarrée.
    Utilisé par Docker pour savoir si le container est vivant.
    """
    settings = get_settings()
    uptime = (datetime.now(UTC) - _start_time).total_seconds()

    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(uptime, 2),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get(
    "/ready",
    summary="Readiness check",
    description="Vérifie que toutes les dépendances (PostgreSQL, Redis, etc.) sont accessibles.",
)
async def ready() -> dict[str, Any]:
    """
    Readiness check.
    Vérifie la connectivité avec chaque service externe.
    Retourne 200 si tout est OK, 503 si au moins un service est indisponible.

    Utilisé par les load balancers pour router le trafic uniquement
    vers les instances prêtes.
    """
    from fastapi import HTTPException
    from app.db.database import check_database_connection
    checks: dict[str, Any] = {}
    all_healthy = True

    # PostgreSQL
    db_ok = await check_database_connection()
    checks["postgresql"] = {"status": "ok" if db_ok else "error"}
    if not db_ok:
        all_healthy = False

    # Redis
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis.url, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        checks["redis"] = {"status": "ok"}
    except Exception as exc:
        checks["redis"] = {"status": "error", "detail": "unreachable"}
        all_healthy = False
        logger.warning("Redis health check failed", error=str(exc))

    # RabbitMQ (optionnel selon feature flag)
    if settings.feature_rabbitmq_enabled:
        try:
            import aio_pika
            connection = await aio_pika.connect_robust(
                settings.rabbitmq.url,
                timeout=3,
            )
            await connection.close()
            checks["rabbitmq"] = {"status": "ok"}
        except Exception as exc:
            checks["rabbitmq"] = {"status": "error", "detail": "unreachable"}
            all_healthy = False
            logger.warning("RabbitMQ health check failed", error=str(exc))

    # Neo4j (optionnel selon feature flag)
    if settings.feature_neo4j_enabled:
        try:
            from neo4j import AsyncGraphDatabase
            driver = AsyncGraphDatabase.driver(
                settings.neo4j.uri,
                auth=(settings.neo4j.user, settings.neo4j.password),
            )
            await driver.verify_connectivity()
            await driver.close()
            checks["neo4j"] = {"status": "ok"}
        except Exception as exc:
            checks["neo4j"] = {"status": "error", "detail": "unreachable"}
            all_healthy = False
            logger.warning("Neo4j health check failed", error=str(exc))

    response = {
        "status": "ready" if all_healthy else "degraded",
        "checks": checks,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    if not all_healthy:
        raise HTTPException(status_code=503, detail=response)

    return response
