"""CLI Test Runner for AuraScribe Clinical AI Agent.

Allows testing your agent locally or against your llama.cpp / Ollama / OpenAI server.
Usage:
    python run_agent.py
    python run_agent.py "Dok, masakit po ang lalamunan ko at nilalagnat simula kahapon."
"""

import sys
import json
import urllib.request
import urllib.error
from aurascribe.schemas.transcript import ValidatedTranscript, TranscriptMetadata
from aurascribe.agent.clinical_agent import ClinicalExtractionAgent
from aurascribe.utils.config import get_settings


def check_endpoint(url: str, timeout: float = 2.0) -> bool:
    """Verifies if the configured local or remote inference server is responsive."""
    try:
        # Check standard health or models route
        health_url = url.rstrip("/")
        if health_url.endswith("/v1"):
            health_url += "/models"
        else:
            health_url += "/v1/models"
            
        req = urllib.request.Request(health_url, headers={"User-Agent": "AuraScribe/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 204)
    except Exception:
        return False


def main():
    settings = get_settings()

    print("==================================================")
    print(" 🩺 AuraScribe Clinical Agent Diagnostics & Runner")
    print("==================================================")
    print(f"Environment:       {settings.aurascribe_env}")
    print(f"LLM Provider:      {settings.llm_provider}")
    print(f"Target Model:      {settings.llm_model}")
    print(f"Target Language:   {settings.target_language}")

    active_endpoint = None
    if settings.llm_provider in ("llama_cpp", "llamacpp"):
        active_endpoint = settings.llama_cpp_base_url
        print(f"llama.cpp URL:     {active_endpoint}")
    elif settings.llm_provider == "ollama":
        active_endpoint = settings.ollama_base_url
        print(f"Ollama URL:        {active_endpoint}")
    elif settings.llm_provider == "custom":
        active_endpoint = settings.custom_base_url
        print(f"Custom URL:        {active_endpoint}")
    print("--------------------------------------------------")

    # Sample dialogue or user CLI input
    if len(sys.argv) > 1:
        dialogue = " ".join(sys.argv[1:])
    else:
        dialogue = (
            "Pasyente: Dok, dalawang araw na po akong nilalagnat at masakit ang lalamunan ko. "
            "Doktor: May ubo ka ba o hirap sa paghinga? "
            "Pasyente: Wala naman po, pero mahapdi lumunok at nanghihina po ako."
        )

    print(f"Sample Dialogue:\n\"{dialogue}\"\n")

    # Check server availability
    server_online = False
    if active_endpoint:
        print(f"Checking connection to: {active_endpoint} ...")
        server_online = check_endpoint(active_endpoint)
        if server_online:
            print("Server Status:     🟢 ONLINE & RESPONSIVE")
        else:
            print("Server Status:     🟡 OFFLINE / UNREACHABLE")
            if settings.llm_provider in ("llama_cpp", "llamacpp"):
                print("\nTo start your llama.cpp server, run on your machine / philgood:")
                print("  llama-server -m ./models/qwen2.5-7b-instruct-q4_k_m.gguf --host 0.0.0.0 --port 8080 -ngl 99 -c 16384\n")
            elif settings.llm_provider == "ollama":
                print("\nTo start Ollama, run:")
                print("  ollama serve\n")

    print("--------------------------------------------------")
    print("Initializing Clinical Extraction Agent...")
    agent = ClinicalExtractionAgent(settings=settings)

    transcript = ValidatedTranscript(
        text=dialogue,
        metadata=TranscriptMetadata(
            model=settings.transcription_model,
            detected_language="auto",
            duration_seconds=15.0,
        ),
    )

    if not server_online and settings.llm_provider in ("llama_cpp", "ollama", "custom"):
        print("Note: Running pipeline schema & guardrails validation check with TestModel.")
        from pydantic_ai.models.test import TestModel
        from aurascribe.schemas.soap import SOAPNote, Subjective, Objective, Assessment, Plan, Medication
        
        simulated_note = SOAPNote(
            subjective=Subjective(
                chief_complaint="Masakit ang lalamunan at nilalagnat (Sore throat and fever for 2 days)",
                symptoms=["Masakit ang lalamunan (Odynophagia)", "Lagnat (Fever for 2 days)", "Panghihina (Malaise)"],
                history="Denies cough, denies dyspnea (walang ubo, walang hirap sa paghinga).",
            ),
            objective=Objective(
                examination_findings="Erythematous posterior pharyngeal wall without tonsillar exudates.",
            ),
            assessment=Assessment(
                clinical_impression="Acute Pharyngitis, likely viral",
                supporting_evidence=["2-day fever", "Odynophagia / sore throat", "Pharyngeal erythema"],
            ),
            plan=Plan(
                medications=[
                    Medication(name="Paracetamol", dosage="500 mg", frequency="Every 4-6 hours PRN for fever", route="oral")
                ],
                treatment="Warm saline gargling, oral rehydration, voice rest.",
                follow_up="Follow up in 3 days if fever does not subside or difficulty breathing occurs.",
            ),
            review_required=True,
        )
        agent = ClinicalExtractionAgent(settings=settings, model=TestModel(custom_output_args=simulated_note.model_dump()))

    print("Extracting structured SOAP note ...")
    try:
        soap_note = agent.extract_soap_sync(transcript)
        print("\n✅ Extraction Successful!")
        print("==================================================")
        print(" 📋 STRUCTURED CLINICAL SOAP NOTE")
        print("==================================================")
        print(f"Review Required:        {soap_note.review_required}")
        print(f"Chief Complaint:        {soap_note.subjective.chief_complaint}")
        print(f"Symptoms:               {soap_note.subjective.symptoms}")
        print(f"Subjective History:     {soap_note.subjective.history}")
        print(f"Clinical Impression:    {soap_note.assessment.clinical_impression}")
        print(f"Supporting Evidence:    {soap_note.assessment.supporting_evidence}")
        meds_summary = [f"{m.name} {m.dosage or ''} ({m.frequency or ''})".strip() for m in soap_note.plan.medications]
        print(f"Medications:            {meds_summary}")
        print(f"Treatment / Care:       {soap_note.plan.treatment}")
        print(f"Follow-up:              {soap_note.plan.follow_up}")
        print(f"Validation Warnings:    {soap_note.validation_warnings}")
        print("==================================================")
    except Exception as e:
        print(f"\n❌ Error during extraction: {type(e).__name__}: {e}")
        print("\nCheck that your inference server is running and matches your .env settings.")


if __name__ == "__main__":
    main()
