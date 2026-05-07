from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'lung_nodule_followup.db'}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def migrate_sqlite_schema() -> None:
    with engine.begin() as conn:
        tables = [row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))]
        if "nodule_annotations" in tables:
            columns = [row[1] for row in conn.execute(text("PRAGMA table_info(nodule_annotations)"))]
            if "nodule_id" not in columns:
                conn.execute(text("ALTER TABLE nodule_annotations ADD COLUMN nodule_id INTEGER"))
        if "image_slices" in tables:
            columns = [row[1] for row in conn.execute(text("PRAGMA table_info(image_slices)"))]
            if "dicom_path" not in columns:
                conn.execute(text("ALTER TABLE image_slices ADD COLUMN dicom_path VARCHAR(512)"))
        if "nodule_measurements" in tables:
            columns = [row[1] for row in conn.execute(text("PRAGMA table_info(nodule_measurements)"))]
            for name in ("min_hu", "max_hu", "roi_area_mm2"):
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE nodule_measurements ADD COLUMN {name} FLOAT"))
        if "analysis_results" in tables:
            columns = [row[1] for row in conn.execute(text("PRAGMA table_info(analysis_results)"))]
            if "nodule_id" not in columns:
                conn.execute(text("ALTER TABLE analysis_results ADD COLUMN nodule_id INTEGER"))
        if "reports" in tables:
            columns = [row[1] for row in conn.execute(text("PRAGMA table_info(reports)"))]
            report_columns = {
                "doctor_opinion": "TEXT DEFAULT ''",
                "followup_plan": "TEXT DEFAULT ''",
                "status": "VARCHAR(32) DEFAULT 'draft'",
                "finalized_at": "DATETIME",
            }
            for name, definition in report_columns.items():
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE reports ADD COLUMN {name} {definition}"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
