"""Pydantic v2 schemas for SOAP (Subjective, Objective, Assessment, Plan) clinical documentation.

Enforces strict typing, distinguishes absent fields (None) from explicitly negative findings,
and mandates human physician verification before any clinical utilization.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class VitalSigns(BaseModel):
    """Structured vital signs explicitly reported or observed."""

    blood_pressure: Optional[str] = Field(
        default=None,
        description="Blood pressure reading (e.g. '120/80 mmHg') if explicitly stated.",
    )
    heart_rate: Optional[str] = Field(
        default=None,
        description="Pulse or heart rate (e.g. '78 bpm') if explicitly stated.",
    )
    respiratory_rate: Optional[str] = Field(
        default=None,
        description="Respiratory rate (e.g. '18 breaths/min') if explicitly stated.",
    )
    temperature: Optional[str] = Field(
        default=None,
        description="Body temperature (e.g. '37.8 C') if explicitly stated.",
    )
    oxygen_saturation: Optional[str] = Field(
        default=None,
        description="Pulse oximetry reading (e.g. '98% on room air') if explicitly stated.",
    )
    weight: Optional[str] = Field(
        default=None,
        description="Patient weight (e.g. '65 kg') if explicitly stated.",
    )


class Medication(BaseModel):
    """Explicitly mentioned or prescribed medication entry."""

    name: str = Field(..., description="Medication name (generic or brand).")
    dosage: Optional[str] = Field(
        default=None,
        description="Dosage strength (e.g. '500 mg') if explicitly mentioned.",
    )
    frequency: Optional[str] = Field(
        default=None,
        description="Dosing interval or frequency (e.g. 'twice daily after meals').",
    )
    route: Optional[str] = Field(
        default=None,
        description="Route of administration (e.g. 'oral', 'topical', 'IV').",
    )
    instructions: Optional[str] = Field(
        default=None,
        description="Specific instructions or duration (e.g. 'for 7 days').",
    )


class DiagnosticTest(BaseModel):
    """Explicitly ordered or discussed diagnostic/laboratory investigation."""

    name: str = Field(..., description="Investigation name (e.g. 'CBC', 'Chest X-ray').")
    reason: Optional[str] = Field(
        default=None,
        description="Clinical rationale or indication if explicitly noted in the discussion.",
    )
    instructions: Optional[str] = Field(
        default=None,
        description="Patient preparation or scheduling instructions if mentioned.",
    )


class Subjective(BaseModel):
    """Subjective information communicated directly by the patient or caregiver."""

    chief_complaint: Optional[str] = Field(
        default=None,
        description="Primary reason for the visit in patient's words or standard summary.",
    )
    symptoms: List[str] = Field(
        default_factory=list,
        description="Reported symptoms explicitly mentioned by the patient.",
    )
    history: Optional[str] = Field(
        default=None,
        description="History of present illness, relevant past medical history, or chronicity.",
    )
    associated_symptoms: List[str] = Field(
        default_factory=list,
        description="Secondary or associated symptoms reported by the patient.",
    )


class Objective(BaseModel):
    """Objective clinical data observed, measured, or examined by healthcare personnel."""

    vital_signs: Optional[VitalSigns] = Field(
        default=None,
        description="Objectively recorded or reported vital sign measurements.",
    )
    examination_findings: Optional[str] = Field(
        default=None,
        description="Physical examination findings documented during the encounter.",
    )
    observations: List[str] = Field(
        default_factory=list,
        description="Clinician observations (e.g. patient appears pale, acute distress).",
    )


class Assessment(BaseModel):
    """Clinical impression and diagnostic reasoning derived strictly from dialogue."""

    clinical_impression: Optional[str] = Field(
        default=None,
        description="Working impression or differential diagnosis explicitly mentioned.",
    )
    supporting_evidence: List[str] = Field(
        default_factory=list,
        description="Explicit transcript findings corroborating the clinical impression.",
    )
    uncertainties: List[str] = Field(
        default_factory=list,
        description="Unresolved clinical ambiguities, contradictions, or pending inquiries.",
    )


class Plan(BaseModel):
    """Management, diagnostic, and follow-up strategy discussed or ordered."""

    medications: List[Medication] = Field(
        default_factory=list,
        description="Explicitly prescribed, renewed, or adjusted medications.",
    )
    tests: List[DiagnosticTest] = Field(
        default_factory=list,
        description="Explicitly ordered laboratory, imaging, or diagnostic procedures.",
    )
    treatment: Optional[str] = Field(
        default=None,
        description="Non-pharmacological treatment, patient guidance, or home care advice.",
    )
    follow_up: Optional[str] = Field(
        default=None,
        description="Follow-up timeframe, return precautions, or referral instructions.",
    )


class SOAPNote(BaseModel):
    """Complete structured clinical documentation model conforming to SOAP standards."""

    subjective: Subjective = Field(
        default_factory=Subjective,
        description="Subjective patient reports.",
    )
    objective: Objective = Field(
        default_factory=Objective,
        description="Objective clinician observations and physical findings.",
    )
    assessment: Assessment = Field(
        default_factory=Assessment,
        description="Clinical assessment and diagnostic synthesis.",
    )
    plan: Plan = Field(
        default_factory=Plan,
        description="Therapeutic and diagnostic plan.",
    )
    review_required: bool = Field(
        default=True,
        description="Mandatory physician review requirement flag (always True).",
    )
    validation_warnings: List[str] = Field(
        default_factory=list,
        description="Automated clinical safety warnings or noted ambiguities.",
    )

