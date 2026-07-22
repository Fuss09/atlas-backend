"""
Atlas - API v1 Router
=====================
Agrège tous les routeurs de l'API v1.
"""

from fastapi import APIRouter, Depends

from app.api.deps import require_authenticated
from app.api.v1.endpoints import auth, catalysts, companies, company_import, discovery, events, graph, health, opportunity, snapshots, themes, watchlist

router = APIRouter()

router.include_router(health.router)
router.include_router(auth.router)
router.include_router(company_import.router, dependencies=[Depends(require_authenticated)])
router.include_router(companies.router, dependencies=[Depends(require_authenticated)])
router.include_router(themes.router, dependencies=[Depends(require_authenticated)])
router.include_router(themes.companies_router, dependencies=[Depends(require_authenticated)])
router.include_router(discovery.router, dependencies=[Depends(require_authenticated)])
router.include_router(discovery.companies_router, dependencies=[Depends(require_authenticated)])
router.include_router(events.router, dependencies=[Depends(require_authenticated)])
router.include_router(events.companies_router, dependencies=[Depends(require_authenticated)])
router.include_router(opportunity.router, dependencies=[Depends(require_authenticated)])
router.include_router(opportunity.companies_router, dependencies=[Depends(require_authenticated)])
router.include_router(graph.router, dependencies=[Depends(require_authenticated)])
router.include_router(graph.companies_router, dependencies=[Depends(require_authenticated)])
router.include_router(watchlist.router, dependencies=[Depends(require_authenticated)])
router.include_router(snapshots.companies_router, dependencies=[Depends(require_authenticated)])
router.include_router(catalysts.router, dependencies=[Depends(require_authenticated)])
router.include_router(catalysts.companies_router, dependencies=[Depends(require_authenticated)])
