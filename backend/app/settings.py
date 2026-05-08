from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("LNF_DATABASE_URL", f"sqlite:///{BASE_DIR / 'lung_nodule_followup.db'}")
UPLOAD_DIR = Path(os.getenv("LNF_UPLOAD_DIR", str(BASE_DIR / "uploads")))
STUDY_DATA_DIR = Path(os.getenv("LNF_STUDY_DATA_DIR", str(BASE_DIR / "study_data")))
MODEL_ARTIFACT_DIR = Path(os.getenv("LNF_MODEL_ARTIFACT_DIR", str(BASE_DIR / "model_artifacts")))
