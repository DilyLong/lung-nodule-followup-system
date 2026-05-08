from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

with TemporaryDirectory() as temp_dir:
    os.environ["LNF_DATABASE_URL"] = f"sqlite:///{Path(temp_dir) / 'smoke.db'}"
    os.environ["LNF_UPLOAD_DIR"] = str(Path(temp_dir) / "uploads")
    os.environ["LNF_STUDY_DATA_DIR"] = str(Path(temp_dir) / "study_data")
    os.environ["LNF_MODEL_ARTIFACT_DIR"] = str(Path(temp_dir) / "model_artifacts")

    from fastapi.testclient import TestClient

    from app.main import app

    def _csv_upload(code: str) -> dict[str, tuple[str, bytes, str]]:
        files = {
            "patients": ("patients.csv", f"patient_code,name,sex,age,smoking_history,family_history,primary_diagnosis\n{code},Smoke测试,男,60,既往吸烟,无,肺结节随访\n"),
            "studies": ("studies.csv", f"patient_code,study_date,modality,dicom_relative_path,scanner,slice_thickness_mm,series_description\n{code},2026-01-01,CT,/dicom/smoke/1,Smoke CT,1.0,薄层肺窗\n{code},2026-04-01,CT,/dicom/smoke/2,Smoke CT,1.0,薄层肺窗\n"),
            "nodules": ("nodules.csv", f"patient_code,nodule_id,nodule_label,lobe,nodule_type,clinical_label,pathology_label,baseline_impression\n{code},N1,Smoke结节,右上叶,部分实性,进展,未手术,smoke check\n"),
            "measurements": ("measurements.csv", f"patient_code,study_date,nodule_id,diameter_mm,volume_mm3,mean_hu,solid_component_percent,spiculation_score,lobulation_score,pleural_retraction_score,measurement_source\n{code},2026-01-01,N1,8.0,268,-520,20,0.1,0.1,0.0,radiologist_report\n{code},2026-04-01,N1,9.2,407,-480,32,0.2,0.2,0.1,radiologist_report\n"),
        }
        return {name: (filename, content.encode("utf-8"), "text/csv") for name, (filename, content) in files.items()}

    def main() -> None:
        with TestClient(app) as client:
            for path in ["/health", "/imports/spec", "/model/status", "/system/status"]:
                response = client.get(path)
                response.raise_for_status()
                print(f"{path} {response.status_code}")

            code = "SMOKE-CHECK-001"
            response = client.post("/imports/preview", files=_csv_upload(code))
            response.raise_for_status()
            assert response.json()["validation"]["valid"] is True
            print(f"/imports/preview {response.status_code}")

            response = client.post("/imports/commit?operator=Smoke测试", files=_csv_upload(code))
            response.raise_for_status()
            payload = response.json()
            assert payload["committed"] is True
            assert payload["batch"]["operator"] == "Smoke测试"
            patient_id = payload["patient_ids"][0]
            print(f"/imports/commit {response.status_code}")

            batches = client.get("/imports/batches")
            batches.raise_for_status()
            batch_id = batches.json()[0]["id"]
            detail = client.get(f"/imports/batches/{batch_id}")
            detail.raise_for_status()
            assert detail.json()["entities"]
            print(f"/imports/batches/{batch_id} {detail.status_code}")

            patient = client.get(f"/patients/{patient_id}")
            patient.raise_for_status()
            nodule_id = patient.json()["nodules"][0]["id"]
            analysis = client.post(f"/analysis/{patient_id}/run?nodule_id={nodule_id}")
            analysis.raise_for_status()
            report = client.post(f"/reports/{analysis.json()['id']}?operator=Smoke测试")
            report.raise_for_status()
            report_id = report.json()["id"]
            versions = client.get(f"/reports/{report_id}/versions")
            audit = client.get(f"/reports/{report_id}/audit")
            versions.raise_for_status()
            audit.raise_for_status()
            assert versions.json()[0]["operator"] == "Smoke测试"
            assert audit.json()[0]["operator"] == "Smoke测试"
            print(f"/reports/{report_id}/versions {versions.status_code}")
            print(f"/reports/{report_id}/audit {audit.status_code}")

            readiness = client.get("/model/training/readiness")
            readiness.raise_for_status()
            assert readiness.json()["eligible_sample_count"] >= 1
            training = client.post("/model/training/run?operator=Smoke测试")
            training.raise_for_status()
            assert training.json()["operator"] == "Smoke测试"
            print(f"/model/training/readiness {readiness.status_code}")
            print(f"/model/training/run {training.status_code}")

            rollback = client.post(f"/imports/batches/{batch_id}/rollback?operator=Smoke测试")
            rollback.raise_for_status()
            assert rollback.json()["operator"] == "Smoke测试"
            print(f"/imports/batches/{batch_id}/rollback {rollback.status_code}")

    if __name__ == "__main__":
        main()
