"""Form Schema Registry and Dynamic Clinical Form Loader.

Provides centralized access to schema definitions for schema-driven, form-agnostic
clinical documentation interfaces (e.g. SOAP Notes, Dental Exams, Triage Records).
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aurascribe.schemas.forms")

# Search directories for form schemas
SCHEMA_DIRS = [
    Path(__file__).parent,
    Path(__file__).parent.parent.parent.parent / "templates" / "forms",
]

_SCHEMA_CACHE: Dict[str, Dict[str, Any]] = {}


def load_form_schema(file_path: Path) -> Optional[Dict[str, Any]]:
    """Loads and parses a single JSON form schema file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "form_id" in data and "sections" in data:
                return data
    except Exception as exc:
        logger.error("Failed to load form schema from %s: %s", file_path, exc)
    return None


def get_form_schema(form_id: str = "soap_note") -> Dict[str, Any]:
    """Retrieves a form schema by form_id, defaulting to 'soap_note'.

    Args:
        form_id: Unique identifier of the requested form schema.

    Returns:
        dict: The parsed form schema dictionary.

    Raises:
        FileNotFoundError: If the requested form schema cannot be located.
    """
    clean_id = (form_id or "soap_note").lower().strip()

    if clean_id in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[clean_id]

    # Search known directories
    for s_dir in SCHEMA_DIRS:
        if not s_dir.exists():
            continue
        candidate = s_dir / f"{clean_id}.json"
        if candidate.exists():
            schema = load_form_schema(candidate)
            if schema:
                _SCHEMA_CACHE[clean_id] = schema
                return schema

    # Fallback to soap_note if specific id not found and it's not already soap_note
    if clean_id != "soap_note":
        logger.warning("Form schema '%s' not found. Falling back to 'soap_note'.", clean_id)
        return get_form_schema("soap_note")

    raise FileNotFoundError(f"Default form schema 'soap_note.json' not found in {SCHEMA_DIRS}")


def list_available_forms() -> List[Dict[str, str]]:
    """Returns a list of all discoverable form templates with metadata."""
    forms: Dict[str, Dict[str, str]] = {}

    for s_dir in SCHEMA_DIRS:
        if not s_dir.exists():
            continue
        for json_file in s_dir.glob("*.json"):
            schema = load_form_schema(json_file)
            if schema and "form_id" in schema:
                fid = schema["form_id"]
                if fid not in forms:
                    forms[fid] = {
                        "form_id": fid,
                        "form_title": schema.get("form_title", fid.replace("_", " ").title()),
                        "form_description": schema.get("form_description", ""),
                    }

    return list(forms.values())


def normalize_extracted_data(extracted_data: Dict[str, Any], form_id: str = "soap_note") -> Dict[str, Any]:
    """Ensures extracted clinical data contains standard fields and aliases.

    This ensures that dot-notation key bindings like `subjective.history_of_present_illness`,
    `assessment.primary_diagnosis`, and `plan.prescriptions` resolve effortlessly
    regardless of whether the LLM produced strict SOAPNote or conversational JSON.
    """
    data = dict(extracted_data)

    # Normalize Subjective fields
    subj = data.get("subjective") or {}
    if isinstance(subj, dict):
        if "history_of_present_illness" not in subj or not subj["history_of_present_illness"]:
            subj["history_of_present_illness"] = subj.get("history") or ""
        if "history" not in subj or not subj["history"]:
            subj["history"] = subj.get("history_of_present_illness") or ""
        if "current_medications" not in subj or not subj["current_medications"]:
            subj["current_medications"] = subj.get("medications") or "None reported"
        if "allergies" not in subj:
            subj["allergies"] = "No Known Drug Allergies (NKDA)"
        data["subjective"] = subj

    # Normalize Objective fields
    obj = data.get("objective") or {}
    if isinstance(obj, dict):
        if "physical_exam" not in obj or not obj["physical_exam"]:
            obj["physical_exam"] = obj.get("examination_findings") or ""
        if "vital_signs" not in obj or not obj["vital_signs"]:
            obj["vital_signs"] = obj.get("vitals") or ""
        data["objective"] = obj
    elif isinstance(obj, str):
        data["objective"] = {
            "vital_signs": "",
            "physical_exam": obj,
        }

    # Normalize Assessment fields
    ass = data.get("assessment") or {}
    if isinstance(ass, dict):
        if "primary_diagnosis" not in ass or not ass["primary_diagnosis"]:
            ass["primary_diagnosis"] = ass.get("clinical_impression") or ""
        if "differential_diagnoses" not in ass or not ass["differential_diagnoses"]:
            uncertainties = ass.get("uncertainties")
            if isinstance(uncertainties, list) and uncertainties:
                ass["differential_diagnoses"] = "; ".join(uncertainties)
            else:
                ass["differential_diagnoses"] = ass.get("differential") or ""
        data["assessment"] = ass
    elif isinstance(ass, str):
        data["assessment"] = {
            "primary_diagnosis": ass,
            "differential_diagnoses": "",
        }

    # Normalize Plan fields
    plan = data.get("plan") or {}
    if isinstance(plan, dict):
        if "prescriptions" not in plan or not plan["prescriptions"]:
            meds = plan.get("medications")
            if isinstance(meds, list) and meds:
                med_strs = []
                for m in meds:
                    if isinstance(m, dict):
                        parts = [m.get("name", "")]
                        if m.get("dosage"):
                            parts.append(m["dosage"])
                        if m.get("frequency"):
                            parts.append(m["frequency"])
                        if m.get("instructions"):
                            parts.append(m["instructions"])
                        med_strs.append(" ".join(filter(None, parts)))
                    else:
                        med_strs.append(str(m))
                plan["prescriptions"] = "\n".join(med_strs)
            else:
                plan["prescriptions"] = str(meds or "")

        if "instructions" not in plan or not plan["instructions"]:
            plan["instructions"] = plan.get("treatment") or plan.get("follow_up") or ""
        data["plan"] = plan
    elif isinstance(plan, str):
        data["plan"] = {
            "prescriptions": "",
            "instructions": plan,
        }

    return data

