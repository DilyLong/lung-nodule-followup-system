from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import DATABASE_URL

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
            if "measurement_source" not in columns:
                conn.execute(text("ALTER TABLE nodule_measurements ADD COLUMN measurement_source VARCHAR(64) DEFAULT 'demo'"))
        if "nodules" in tables:
            columns = [row[1] for row in conn.execute(text("PRAGMA table_info(nodules)"))]
            if "clinical_label" not in columns:
                conn.execute(text("ALTER TABLE nodules ADD COLUMN clinical_label VARCHAR(32) DEFAULT '待定'"))
            if "pathology_label" not in columns:
                conn.execute(text("ALTER TABLE nodules ADD COLUMN pathology_label VARCHAR(64) DEFAULT '未手术'"))
        if "analysis_results" in tables:
            columns = [row[1] for row in conn.execute(text("PRAGMA table_info(analysis_results)"))]
            if "nodule_id" not in columns:
                conn.execute(text("ALTER TABLE analysis_results ADD COLUMN nodule_id INTEGER"))
        expected_tables = {
            "import_batches": "CREATE TABLE IF NOT EXISTS import_batches (id INTEGER PRIMARY KEY, created_at DATETIME, committed_at DATETIME, rolled_back_at DATETIME, status VARCHAR(32), qc_score FLOAT, counts_json TEXT, issues_json TEXT, message TEXT, operator VARCHAR(64) DEFAULT '系统')",
            "import_batch_entities": "CREATE TABLE IF NOT EXISTS import_batch_entities (id INTEGER PRIMARY KEY, batch_id INTEGER, entity_type VARCHAR(32), entity_id INTEGER, action VARCHAR(32), stable_key VARCHAR(256), previous_json TEXT, operator VARCHAR(64) DEFAULT '系统')",
            "report_versions": "CREATE TABLE IF NOT EXISTS report_versions (id INTEGER PRIMARY KEY, report_id INTEGER, version_number INTEGER, created_at DATETIME, status VARCHAR(32), content_markdown TEXT, doctor_opinion TEXT, followup_plan TEXT, operator VARCHAR(64) DEFAULT '系统')",
            "report_audit_logs": "CREATE TABLE IF NOT EXISTS report_audit_logs (id INTEGER PRIMARY KEY, report_id INTEGER, created_at DATETIME, event VARCHAR(64), message TEXT, operator VARCHAR(64) DEFAULT '系统')",
        }
        for table_name, create_sql in expected_tables.items():
            if table_name not in tables:
                conn.execute(text(create_sql))
            columns = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table_name})"))]
            if "operator" not in columns:
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN operator VARCHAR(64) DEFAULT '系统'"))

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
