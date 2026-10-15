import uuid
from persistence.models.medical_record import MedicalRecord


def test_medical_record_instantiation_with_valid_data():
    record = MedicalRecord(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        version=1,
        record_data={"patient_info": {"chief_complaint": "头痛", "complaint_duration": "2天", "complaint_location": "前额"}},
        completion_level="partial",
        missing_core_fields=["past_history.chronic_diseases"],
    )
    assert record.id is not None
    assert record.version == 1
    assert record.completion_level == "partial"
    assert record.record_data["patient_info"]["chief_complaint"] == "头痛"


def test_medical_record_version_default_is_one():
    record = MedicalRecord(id=uuid.uuid4(), session_id=uuid.uuid4(), version=1)
    assert record.version == 1


def test_medical_record_completion_level_default_is_partial():
    record = MedicalRecord(id=uuid.uuid4(), session_id=uuid.uuid4(), completion_level="partial")
    assert record.completion_level == "partial"


def test_medical_record_missing_core_fields_accepts_list():
    record = MedicalRecord(id=uuid.uuid4(), session_id=uuid.uuid4(), missing_core_fields=[])
    assert record.missing_core_fields == []


def test_medical_record_jsonb_round_trip():
    data = {
        "patient_info": {"chief_complaint": "腹痛", "complaint_duration": "3天", "complaint_location": "上腹", "severity": 6, "age": 35, "gender": "男"},
        "accompanying_symptoms": ["恶心", "腹泻"],
        "past_history": {"chronic_diseases": ["胃炎"], "current_medications": []},
        "allergy_history": {"drug_allergies": ["青霉素"]},
    }
    record = MedicalRecord(id=uuid.uuid4(), session_id=uuid.uuid4(), record_data=data)
    assert record.record_data["patient_info"]["chief_complaint"] == "腹痛"
    assert record.record_data["accompanying_symptoms"] == ["恶心", "腹泻"]
    assert "胃炎" in record.record_data["past_history"]["chronic_diseases"]
