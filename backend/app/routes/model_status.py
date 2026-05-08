from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..pipeline.model import model_runtime_status, run_model_self_check
from ..pipeline.training import train_temporal_model, training_readiness
from ..seed import seed_demo_data
from ..schemas import ModelSelfCheckReport, ModelTrainingReadiness, ModelTrainingReport

router = APIRouter(prefix="/model", tags=["model"])


@router.get("/status")
def get_model_status() -> dict:
    return model_runtime_status()


@router.post("/self-check", response_model=ModelSelfCheckReport)
def self_check_model() -> dict:
    return run_model_self_check()


@router.get("/training/readiness", response_model=ModelTrainingReadiness)
def get_training_readiness(db: Session = Depends(get_db)) -> dict:
    return training_readiness(db)


@router.post("/training/run", response_model=ModelTrainingReport)
def run_training(operator: str = "系统", db: Session = Depends(get_db)) -> dict:
    return train_temporal_model(db, operator)


@router.post("/training/demo-cohort")
def load_demo_training_cohort(db: Session = Depends(get_db)) -> dict:
    result = seed_demo_data(db)
    return {"loaded": True, "message": "Synthetic demo cohort is available for local training demonstration.", **result}
