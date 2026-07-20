"""
Atlas - API v1 Router
=====================
Agrège tous les routeurs de l'API v1.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, companies, discovery, events, graph, health, opportunity, themes, watchlist

router = APIRouter()

router.include_router(health.router)
router.include_router(auth.router)
router.include_router(companies.router)
router.include_router(themes.router)
router.include_router(themes.companies_router)
router.include_router(discovery.router)
router.include_router(discovery.companies_router)
router.include_router(events.router)
router.include_router(events.companies_router)
router.include_router(opportunity.router)
router.include_router(opportunity.companies_router)
router.include_router(graph.router)
router.include_router(graph.companies_router)
router.include_router(watchlist.router)
