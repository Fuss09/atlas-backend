"""
Atlas - Company Import Endpoint
===============================

POST /companies/import — Importer une entreprise réelle par son ticker (public)

201 si créée, 200 si le ticker existait déjà (idempotent), 404 si le ticker
est introuvable chez le fournisseur de données.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import DbSession
from app.schemas.company import CompanyResponse
from app.schemas.company_import import CompanyImportRequest
from app.services.company_import import CompanyImportService

router = APIRouter(prefix="/companies", tags=["Companies"])


async def get_import_service(db: DbSession) -> CompanyImportService:
    return CompanyImportService(db)


ImportServiceDep = Annotated[CompanyImportService, Depends(get_import_service)]


@router.post(
    "/import",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Importer une entreprise réelle par ticker",
)
async def import_company(
    payload: CompanyImportRequest,
    service: ImportServiceDep,
    response: Response,
) -> CompanyResponse:
    company, created = await service.import_by_ticker(payload.ticker, payload.exchange)
    if not created:
        response.status_code = status.HTTP_200_OK
    return CompanyResponse.model_validate(company)
