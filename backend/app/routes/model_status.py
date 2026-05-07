from __future__ import annotations

from fastapi import APIRouter

from ..pipeline.model import model_runtime_status

router = APIRouter(prefix="/model", tags=["model"])


@router.get("/status")
def get_model_status() -> dict:
    return model_runtime_status()
