from fastapi import FastAPI, Depends, HTTPException, status, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from config import settings
from routers import units, meters, residents, residencies, import_csv

app = FastAPI(
    title="Metering Admin API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="metering_admin_session",
    max_age=8 * 60 * 60,   # 8 Stunden
    https_only=False,       # auf True setzen wenn HTTPS vorhanden
)


# ── Auth-Hilfsfunktionen ──────────────────────────────────────────────────────

def require_auth(request: Request):
    if not request.session.get("authenticated"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nicht eingeloggt",
        )


# ── Login / Logout ────────────────────────────────────────────────────────────

@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse("/app/static/login.html")


@app.post("/login", include_in_schema=False)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    import secrets
    ok_user = secrets.compare_digest(username, settings.admin_username)
    ok_pass = secrets.compare_digest(password, settings.admin_password)
    if ok_user and ok_pass:
        request.session["authenticated"] = True
        return RedirectResponse(url="/", status_code=303)
    return HTMLResponse(
        content=login_html(error="Ungültige Zugangsdaten"),
        status_code=401,
    )


@app.get("/logout", include_in_schema=False)
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# ── Routers ───────────────────────────────────────────────────────────────────

for router in [units.router, meters.router, residents.router,
               residencies.router, import_csv.router]:
    app.include_router(router, prefix="/api", dependencies=[Depends(require_auth)])


# ── Static Frontend ───────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="/app/static"), name="static")


@app.get("/", include_in_schema=False)
def root(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login")
    return FileResponse("/app/static/index.html")


def login_html(error: str = "") -> str:
    """Fallback falls login.html nicht gefunden wird."""
    return f"""<!DOCTYPE html><html><body>
    <form method='post' action='/login'>
        <input name='username' placeholder='Benutzer'><br>
        <input name='password' type='password' placeholder='Passwort'><br>
        <button type='submit'>Einloggen</button>
        <p style='color:red'>{error}</p>
    </form></body></html>"""