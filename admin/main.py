from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse
import secrets
from .config import settings
from .routers import units, meters, residents, residencies, import_csv

app = FastAPI(
    title="Metering Admin API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── HTTP Basic Auth (einfache Absicherung ohne externes Auth-System) ───────────
security = HTTPBasic()

def require_auth(credentials: HTTPBasicCredentials = Depends(security)):
    ok_user = secrets.compare_digest(credentials.username, settings.admin_username)
    ok_pass = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültige Zugangsdaten",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# ── Routers ───────────────────────────────────────────────────────────────────
for router in [units.router, meters.router, residents.router,
               residencies.router, import_csv.router]:
    app.include_router(router, prefix="/api", dependencies=[Depends(require_auth)])

# ── Static Frontend ───────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="/app/static"), name="static")

@app.get("/", include_in_schema=False)
def root():
    return FileResponse("/app/static/index.html")