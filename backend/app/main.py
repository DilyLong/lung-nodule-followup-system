from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, SessionLocal, engine, migrate_sqlite_schema
from .routes import analysis, annotations, demo, exports, followup, imaging, imports, matching, model_status, patients, reports, system_status, uploads
from .seed import seed_demo_data

app = FastAPI(
    title="肺结节多期 CT 智能随访系统",
    description="三维配准、时序特征提取、ConvLSTM 风险评估与个体化随访建议的本地 MVP。",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    migrate_sqlite_schema()
    db = SessionLocal()
    try:
        seed_demo_data(db)
    finally:
        db.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(patients.router)
app.include_router(uploads.router)
app.include_router(imaging.router)
app.include_router(annotations.router)
app.include_router(matching.router)
app.include_router(followup.router)
app.include_router(analysis.router)
app.include_router(reports.router)
app.include_router(exports.router)
app.include_router(imports.router)
app.include_router(demo.router)
app.include_router(model_status.router)
app.include_router(system_status.router)
