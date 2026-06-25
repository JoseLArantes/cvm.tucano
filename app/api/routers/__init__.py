from fastapi import APIRouter

from app.api.routers.admin import router as admin_router
from app.api.routers.analise import router as analise_router
from app.api.routers.auth import router as auth_router
from app.api.routers.cgvn import router as cgvn_router
from app.api.routers.companhias import router as companhias_router
from app.api.routers.exportacao import router as exportacao_router
from app.api.routers.fca import router as fca_router
from app.api.routers.financeiro import router as financeiro_router
from app.api.routers.fre import router as fre_router
from app.api.routers.health import router as health_router
from app.api.routers.ipe import router as ipe_router
from app.api.routers.mestre import router as mestre_router
from app.api.routers.usuarios import router as usuarios_router
from app.api.routers.vlmo import router as vlmo_router
from app.updates.router import router as updates_router

public_router = APIRouter()
public_router.include_router(auth_router, tags=["auth"])
public_router.include_router(health_router, tags=["health"])

protected_router = APIRouter()
protected_router.include_router(analise_router, tags=["analise"])
protected_router.include_router(mestre_router, tags=["mestre"])
protected_router.include_router(companhias_router, tags=["companhias"])
protected_router.include_router(exportacao_router)
protected_router.include_router(financeiro_router, tags=["financeiro"])
protected_router.include_router(fca_router, tags=["fca"])
protected_router.include_router(ipe_router, tags=["ipe"])
protected_router.include_router(vlmo_router, tags=["vlmo"])
protected_router.include_router(cgvn_router, tags=["cgvn"])
protected_router.include_router(fre_router, tags=["fre"])
protected_router.include_router(admin_router, tags=["ingestion"])
protected_router.include_router(usuarios_router, tags=["usuarios"])
protected_router.include_router(updates_router, prefix="/updates", tags=["updates"])
