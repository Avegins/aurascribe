# AuraScribe Technical Product Roadmap 🗺️

This document tracks the technical evolution, milestones, and implementation criteria for the **AuraScribe** ambient clinical documentation platform.

For the comprehensive project background, clinical rationale, and user personas, refer to the [Executive Summary](EXECUTIVE_SUMMARY.md).

---

## Strategic Phases & Timeline Overview

| Phase | Horizon | Focus Area | Key Deliverable |
| :---: | :---: | :--- | :--- |
| **Phase 1** | **Q4 2026 – Q1 2027** | Local Scribe, Diarization & Audio Sync | On-premise Whisper container, PyAnnote diarization, interactive word-level audio sync. |
| **Phase 2** | **Q2 2027** | Dialect & Mobile Edge Expansion | Cebuano, Ilocano, and Hiligaynon biasing; offline-capable Mobile PWA. |
| **Phase 3** | **Q3 2027** | EHR & FHIR Standards Interoperability | HL7 FHIR v4 resource bundles, PhilHealth Konsulta / ICD-10 automated coding. |
| **Phase 4** | **Q4 2027** | Enterprise Security & Compliance | Philippine DPA (RA 10173) & HIPAA compliance, PKI digital sign-off, SSO/RBAC. |
| **Phase 5** | **2028+** | Ambient Clinical Intelligence | Passive exam room listening, real-time allergy/drug safety CDS, dialect aftercare instructions. |

---

## Detailed Milestone Specifications

### Phase 1: Near-Term Infrastructure & Acoustic Enhancements (Q4 2026 – Q1 2027)

#### Milestone 1.1: Localized Offline Whisper Inference
* **Goal:** Enable zero-cloud, fully offline speech-to-text for clinics without continuous internet connectivity.
* **Tasks:**
  - [ ] Implement `faster-whisper` CTranslate2 backend service.
  - [ ] Provide Docker configuration for GPU acceleration (CUDA) and Apple Silicon (Metal/MPS).
  - [ ] Integrate local fallback logic in `src/aurascribe/models/transcription_client.py`.
* **Acceptance Criteria:** Audio files process completely offline with under 3-second turnaround for a 60-second clip on local hardware.

#### Milestone 1.2: Acoustic Speaker Diarization
* **Goal:** Automatically attribute spoken dialogue to `Doctor:`, `Patient:`, or `Accompanying Relative:` using voice embeddings.
* **Tasks:**
  - [ ] Integrate `pyannote.audio` speaker segmentation pipeline.
  - [ ] Correlate speaker turns with timestamped Whisper transcript segments.
  - [ ] Pass pre-attributed turns to the Transcript Cleaning Agent.
* **Acceptance Criteria:** Over 90% turn-attribution accuracy in 2-party and 3-party consultation recordings.

#### Milestone 1.3: Interactive Audio-Transcript Scrubbing
* **Goal:** Clinicians can click any line or bubble in the recorded conversation to jump the audio player directly to that spoken segment.
* **Tasks:**
  - [ ] Capture word-level and sentence-level start/end timestamps from Whisper verbose JSON.
  - [ ] Add `data-start` and `data-end` attributes to dialogue bubbles in `templates/index.html`.
  - [ ] Wire audio playback seeking in `static/js/recorder.js`.
* **Acceptance Criteria:** Clicking a dialogue bubble plays the corresponding audio segment with sub-second precision.

#### Milestone 1.4: Specialty Form Template Library
* **Goal:** Expand schema-driven form templates to key medical specialties.
* **Tasks:**
  - [ ] Author `pediatric_exam.json` (growth percentiles, immunization tracking, developmental milestones).
  - [ ] Author `obgyn_consult.json` (gravida/para, gestational age, ultrasound notes).
  - [ ] Author `orthopedic_evaluation.json` (range of motion, spine alignment, radiological findings).
* **Acceptance Criteria:** All templates dynamically render and scrape clean JSON using `renderDynamicForm()`.

---

### Phase 2: Regional Dialect & Mobile Edge Expansion (Q2 2027)

#### Milestone 2.1: Expanded Philippine Dialect Biasing Dictionaries
* **Goal:** Support the top 5 Philippine regional languages with specialized medical vocabulary hints.
* **Tasks:**
  - [ ] Build lexical dictionaries for **Cebuano / Bisaya** (*"sakit ang dughan"*, *"hilantan"*, *"wala pa koy tambal"*).
  - [ ] Build lexical dictionaries for **Ilocano** (*"nagsakit ti tian"*, *"agpudpudot"*, *"awan agas"*).
  - [ ] Build lexical dictionaries for **Hiligaynon / Ilonggo** (*"masakit ang ulo"*, *"hilanat"*, *"wala bulong"*).
  - [ ] Update language selection controls and automatic dialect detection heuristics.
* **Acceptance Criteria:** Word Error Rate (WER) on regional consultations decreases below 8%.

#### Milestone 2.2: Mobile Progressive Web App (PWA) with Offline Queueing
* **Goal:** Allow doctors and rural health workers to record consultations on tablets or mobile phones without network access.
* **Tasks:**
  - [ ] Configure web app manifest, service workers, and application shell caching.
  - [ ] Implement client-side IndexedDB audio blob storage queue.
  - [ ] Background sync queue that dispatches audio for processing once connectivity is restored.
* **Acceptance Criteria:** Offline recordings persist across browser restarts and automatically ingest when online.

---

### Phase 3: Clinical EHR & FHIR Standards Interoperability (Q3 2027)

#### Milestone 3.1: HL7 FHIR v4 Resource Mapping
* **Goal:** Output interoperable clinical records conformant with international healthcare data exchange standards.
* **Tasks:**
  - [ ] Develop FHIR converter module (`src/aurascribe/interop/fhir.py`).
  - [ ] Map Subjective/Objective fields to `Observation` and `Condition` resources.
  - [ ] Map Prescriptions to `MedicationRequest` resources with standard RxNorm / PNDF codes.
  - [ ] Bundle into a validated FHIR `Encounter` transaction bundle.
* **Acceptance Criteria:** Generated bundles validate against HL7 FHIR v4 schema validators with zero errors.

#### Milestone 3.2: Automated PhilHealth Konsulta & ICD-10 Coding
* **Goal:** Streamline health insurance reimbursement in the Philippines.
* **Tasks:**
  - [ ] Incorporate an ICD-10 diagnostic coding cross-reference service.
  - [ ] Suggest PhilHealth Relative Value Scale (RVS) procedure codes based on the Plan section.
  - [ ] Provide clinician review interface before attaching codes to the signed encounter.
* **Acceptance Criteria:** Accurate diagnostic code suggestions for the top 50 primary outpatient conditions.

---

### Phase 4: Enterprise Security, Governance & Regulatory Compliance (Q4 2027)

#### Milestone 4.1: Philippine DPA (RA 10173) & HIPAA Certification
* **Goal:** Full regulatory compliance and independent data privacy audit.
* **Tasks:**
  - [ ] Deploy client-side or ingress PHI de-identification using Presidio / NER models.
  - [ ] Enforce AES-256 data-at-rest encryption and TLS 1.3 transport security.
  - [ ] Establish Data Privacy Impact Assessments (DPIA) and audit logs.
* **Acceptance Criteria:** Passed third-party security and privacy audit with zero high-severity findings.

#### Milestone 4.2: Cryptographic Physician Sign-Off & PKI
* **Goal:** Legally binding digital signatures for verified clinical notes.
* **Tasks:**
  - [ ] Integrate digital signing using physician PKI certificates or Philippine National PKI (PNPKI).
  - [ ] Generate tamper-evident, SHA-256 signed PDF encounter summaries with verification QR codes.
* **Acceptance Criteria:** Exported PDF notes verify against the issuing hospital's certificate authority.

---

### Phase 5: Ambient Clinical Intelligence & Proactive Care (2028+)

#### Milestone 5.1: Hands-Free Ambient Room Intake
* **Goal:** Passive room recording that activates automatically upon doctor-patient dialogue.
* **Tasks:**
  - [ ] Deploy Voice Activity Detection (Silero VAD) with clinical room noise calibration.
  - [ ] Support wake-word triggers (*"AuraScribe, begin consult"*).
* **Acceptance Criteria:** Eliminates all manual button clicks from the physician's workflow.

#### Milestone 5.2: Multilingual Patient Aftercare Synthesis
* **Goal:** Improve patient treatment adherence by providing discharge summaries in their native spoken tongue.
* **Tasks:**
  - [ ] Automatically synthesize a simplified patient instruction card in the consultation's primary dialect (e.g. Central Bikol).
  - [ ] Provide SMS / WhatsApp / print-ready discharge instructions with dosage schedules.
* **Acceptance Criteria:** Patient comprehension scores increase by >35% compared to standard English printed slips.

---

## Technical Architecture Evolution

```
Current Architecture (MVP v1.2)          Target Architecture (Enterprise v3.0)
─────────────────────────────────        ─────────────────────────────────────
• Single-host Flask App                  • Microservices on Kubernetes
• In-memory audio processing             • Async Celery/Redis queue for audio
• Hybrid Groq / Ollama backend           • On-premise faster-whisper + vLLM cluster
• Form-Agnostic JSON Schemas             • Form-Agnostic Schemas + HL7 FHIR v4
• Browser MediaRecorder capture          • PWA + Ambient Room Mic Arrays + Mobile App
• Browser Local Review                   • SMART-on-FHIR embedded in Hospital EMR
```

---

*For contributions, feature requests, or clinical pilot proposals, please file an issue or contact the project maintainers.*

