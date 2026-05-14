from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os

from database import engine, SessionLocal
import models
from routers import auth_router, b2c_router, b2b_router, surveys_router, messages_router
from seed import seed_database

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="РейтСкан API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(b2c_router.router)
app.include_router(b2b_router.router)
app.include_router(surveys_router.router)
app.include_router(messages_router.router)


@app.on_event("startup")
def on_startup():
    from sqlalchemy import text
    with engine.connect() as conn:
        for col, typedef in [
            ("last_game_play", "DATETIME"),
            ("game_points_today", "INTEGER DEFAULT 0"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {typedef}"))
                conn.commit()
            except Exception:
                pass
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()


# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def root():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.get("/b2c")
def b2c_page():
    return FileResponse(os.path.join(static_dir, "b2c.html"))


@app.get("/b2b")
def b2b_page():
    return FileResponse(os.path.join(static_dir, "b2b.html"))
