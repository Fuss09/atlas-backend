"""
Atlas - Application Factory
============================
Point d'entrée de l'application FastAPI.

Pattern "Application Factory" : la création de l'app est une fonction,
ce qui facilite les tests (chaque test peut créer sa propre instance)
et la configuration dynamique par environnement.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.exception_handlers import register_exception_handlers
from app.api.middleware import RequestLoggingMiddleware
from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Gère le cycle de vie de l'application.
    Code AVANT yield = startup.
    Code APRÈS yield = shutdown.
    """
    settings = get_settings()

    logger.info(
        "Atlas starting up",
        environment=settings.environment,
        version=settings.app_version,
    )

    # Vérification de la connexion à la base de données au démarrage
    from app.db.database import check_database_connection
    db_ok = await check_database_connection()
    if not db_ok:
        logger.error("Cannot connect to database — startup aborted")
        raise RuntimeError("Database connection failed at startup")

    logger.info("All services connected — Atlas is ready")

    yield

    # Shutdown
    logger.info("Atlas shutting down")


def create_app() -> FastAPI:
    """
    Crée et configure l'application FastAPI.

    Returns:
        Instance FastAPI prête à être servie.
    """
    settings = get_settings()

    # Configuration du logging en premier
    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Atlas Market Intelligence — "
            "Plateforme de découverte et d'analyse des opportunités d'investissement."
        ),
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging
    app.add_middleware(RequestLoggingMiddleware)

    # Exception handlers (ordre important : du plus spécifique au plus général)
    register_exception_handlers(app)

    # Routes
    app.include_router(v1_router, prefix=settings.api_prefix)

    # Health checks également disponibles à la racine (pour les load balancers)
    from app.api.v1.endpoints.health import health, ready
    app.add_api_route("/health", health, tags=["Health"])
    app.add_api_route("/ready", ready, tags=["Health"])

    return app


# Instance principale — utilisée par uvicorn
app = create_app()
