from datetime import date

from sqlalchemy.orm import Session

from .models import Nodule, NoduleMeasurement, Patient, Study


def seed_demo_data(db: Session) -> None:
    if db.query(Patient).first():
        return

    patients = [
        Patient(
            patient_code="LN-2026-001",
            name="张某",
            sex="女",
            age=58,
            smoking_history="无吸烟史",
            family_history="无肺癌家族史",
            primary_diagnosis="右上肺混合磨玻璃结节随访",
        ),
        Patient(
            patient_code="LN-2026-002",
            name="李某",
            sex="男",
            age=66,
            smoking_history="吸烟 30 包年，已戒烟",
            family_history="父亲肺癌史",
            primary_diagnosis="左下肺实性结节随访",
        ),
        Patient(
            patient_code="LN-2026-003",
            name="王某",
            sex="女",
            age=49,
            smoking_history="无吸烟史",
            family_history="无",
            primary_diagnosis="右下肺纯磨玻璃结节随访",
        ),
    ]
    db.add_all(patients)
    db.flush()

    demo_specs = [
        {
            "patient": patients[0],
            "nodule": ("主结节", "右上叶尖段", "混合磨玻璃结节", "基线呈混合磨玻璃密度，边界较清"),
            "studies": [
                (date(2024, 5, 10), 8.1, 260.0, -515.0, 18.0, 0.2, 0.2, 0.1),
                (date(2025, 2, 18), 9.0, 345.0, -470.0, 26.0, 0.3, 0.3, 0.2),
                (date(2026, 1, 12), 10.6, 520.0, -395.0, 38.0, 0.5, 0.4, 0.3),
            ],
        },
        {
            "patient": patients[1],
            "nodule": ("主结节", "左下叶背段", "实性结节", "基线为实性小结节，需结合高危因素随访"),
            "studies": [
                (date(2024, 7, 1), 6.2, 125.0, 45.0, 92.0, 0.2, 0.1, 0.1),
                (date(2025, 6, 28), 6.4, 132.0, 48.0, 94.0, 0.2, 0.1, 0.1),
                (date(2026, 4, 2), 6.5, 138.0, 50.0, 95.0, 0.2, 0.1, 0.1),
            ],
        },
        {
            "patient": patients[2],
            "nodule": ("主结节", "右下叶外基底段", "纯磨玻璃结节", "基线为纯磨玻璃密度，形态规则"),
            "studies": [
                (date(2024, 3, 22), 5.8, 102.0, -650.0, 0.0, 0.1, 0.1, 0.0),
                (date(2025, 3, 26), 5.9, 105.0, -642.0, 0.0, 0.1, 0.1, 0.0),
                (date(2026, 3, 19), 5.9, 106.0, -638.0, 0.0, 0.1, 0.1, 0.0),
            ],
        },
    ]

    for index, spec in enumerate(demo_specs, start=1):
        patient = spec["patient"]
        label, lobe, nodule_type, impression = spec["nodule"]
        nodule = Nodule(
            patient_id=patient.id,
            label=label,
            lobe=lobe,
            nodule_type=nodule_type,
            baseline_impression=impression,
        )
        db.add(nodule)
        db.flush()

        for visit_index, row in enumerate(spec["studies"], start=1):
            study_date, diameter, volume, mean_hu, solid_pct, spiculation, lobulation, retraction = row
            study = Study(
                patient_id=patient.id,
                study_date=study_date,
                scanner=f"模拟多排螺旋 CT-{visit_index}",
                slice_thickness_mm=1.0 if visit_index != 2 else 1.25,
                series_description="胸部薄层 CT 平扫",
                status="模拟数据",
            )
            db.add(study)
            db.flush()
            db.add(
                NoduleMeasurement(
                    nodule_id=nodule.id,
                    study_id=study.id,
                    diameter_mm=diameter,
                    volume_mm3=volume,
                    mean_hu=mean_hu,
                    solid_component_percent=solid_pct,
                    spiculation_score=spiculation,
                    lobulation_score=lobulation,
                    pleural_retraction_score=retraction,
                    thumbnail_seed=index * 10 + visit_index,
                )
            )

    db.commit()
