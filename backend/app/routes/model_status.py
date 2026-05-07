from __future__ import annotations

from fastapi import APIRouter

from ..pipeline.model import model_runtime_status, run_model_self_check
from ..schemas import ModelSelfCheckReport

router = APIRouter(prefix="/model", tags=["model"])


@router.get("/status")
def get_model_status() -> dict:
    return model_runtime_status()


@router.post("/self-check", response_model=ModelSelfCheckReport)
def self_check_model() -> dict:
    return run_model_self_check()
