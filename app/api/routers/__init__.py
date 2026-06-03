from fastapi import APIRouter

from app.api.routers.admin import router as admin_router
from app.api.routers.auth import router as auth_router
from app.api.routers.companhias import router as companhias_router
from app.api.routers.financeiro import router as financeiro_router
from app.api.routers.fre import router as fre_router
from app.api.routers.health import router as health_router
from app.api.routers.mestre import router as mestre_router
from app.api.routers.usuarios import router as usuarios_router

public_router = APIRouter()
public_router.include_router(auth_router, tags=["auth"])
public_router.include_router(health_router, tags=["health"])

protected_router = APIRouter()
protected_router.include_router(mestre_router, tags=["mestre"])
protected_router.include_router(companhias_router, tags=["companhias"])
protected_router.include_router(financeiro_router, tags=["financeiro"])
protected_router.include_router(fre_router, tags=["fre"])
protected_router.include_router(admin_router, tags=["admin"])
protected_router.include_router(usuarios_router, tags=["usuarios"])
