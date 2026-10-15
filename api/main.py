
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.database import init_db
from api.routes.sesion import router as sesion_router
from api.routes.temas import router as temas_router

from api.routes.usuarios import router as usuarios_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="NuevaMente API",
    description="Backend de NuevaMente - F08",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(sesion_router)
app.include_router(temas_router)
app.include_router(usuarios_router)


@app.get("/salud")
def verificar_salud():
    return {
        "estado": "ok",
        "servicio": "NuevaMente API",
    }
