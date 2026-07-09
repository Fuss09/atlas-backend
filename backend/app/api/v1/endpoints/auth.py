"""
Atlas - Auth Endpoints
======================
Endpoints d'authentification : register, login, refresh.
"""

from fastapi import APIRouter

from app.api.deps import CurrentUser, UserServiceDep
from app.core.logging import get_logger
from app.schemas.user import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger(__name__)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    summary="Créer un compte",
    description="Inscrit un nouvel utilisateur avec email et mot de passe.",
)
async def register(
    data: RegisterRequest,
    user_service: UserServiceDep,
) -> UserResponse:
    user = await user_service.register(data)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Se connecter",
    description="Authentifie un utilisateur et retourne une paire de tokens JWT.",
)
async def login(
    data: LoginRequest,
    user_service: UserServiceDep,
) -> TokenResponse:
    return await user_service.login(data)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rafraîchir les tokens",
    description="Échange un refresh token valide contre une nouvelle paire de tokens.",
)
async def refresh_tokens(
    data: RefreshTokenRequest,
    user_service: UserServiceDep,
) -> TokenResponse:
    return await user_service.refresh_tokens(data.refresh_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Mon profil",
    description="Retourne le profil de l'utilisateur authentifié.",
)
async def get_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)
