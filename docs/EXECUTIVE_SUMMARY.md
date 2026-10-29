# AuraScribe: Executive Summary & Strategic Product Roadmap 🩺✨

> **Ambient Multilingual Clinical Intelligence for Philippine & Global Healthcare**  
> *Confidential & Proprietary — For Clinical Leadership, Healthcare Administrators, and Engineering Stakeholders*  
> **Document Version:** 2.0.0 | **Last Updated:** October 2026 | **Author:** AuraScribe Engineering & Clinical Informatics Team

---

> [!IMPORTANT]
> **Mandatory Physician Review Policy:**  
> AuraScribe is strictly an ambient clinical documentation aid and pair-programming assistant for clinicians. It does not autonomously diagnose, triage, or prescribe medications. All synthesized transcripts, clinical extractions, and SOAP notes mandate licensed physician verification and formal sign-off prior to clinical utilization or EMR entry.

---

```
                       AURASCRIBE AMBIENT INTELLIGENCE PIPELINE
  ┌─────────────────┐      ┌─────────────────────────┐      ┌────────────────────────┐
  │ Multilingual    │ ───► │ Regional Dialect STT    │ ───► │ Post-Processing Editor │
  │ Consultation    │      │ (Whisper + Prompt Bias) │      │ (Attribution & Clean)  │
  └─────────────────┘      └─────────────────────────┘      └────────────────────────┘
                                                                        │
  ┌─────────────────┐      ┌─────────────────────────┐                  │
  │ Physician Sign  │ ◄─── │ Schema-Driven Dynamic   │ ◄────────────────┘
  │ & EMR Export    │      │ Form Review Interface   │      ┌────────────────────────┐
  └─────────────────┘      └─────────────────────────┘      │ Guardrail Enforcement  │
                                                            │ (Anti-Hallucination)   │
                                                            └────────────────────────┘
```

---

## 1. Executive Summary

### 1.1 WHAT: The Solution
**AuraScribe** is an ambient clinical intelligence and automated medical documentation platform purpose-built for linguistically diverse healthcare environments. Specializing in low-resource and code-switched dialogues common in the Philippines—including **Tagalog, Taglish, Central Bikol, Rinconada, and Albay Bicolano dialects**, alongside English—AuraScribe captures doctor-patient spoken consultations and converts them into verbatim transcripts, cleaned speaker-attributed dialogues, and structured, schema-compliant clinical records (such as **SOAP Notes, Dental Exams, and Triage Records**).

Unlike static documentation forms or raw JSON viewers, AuraScribe features a **Schema-Driven, Form-Agnostic UI** that dynamically renders color-coded, editable form cards (Subjective, Objective, Assessment, Plan). This allows healthcare institutions to support varied clinical templates with zero frontend code modifications while preserving physician oversight and compliance.

---

### 1.2 WHY: The Problem & Clinical Value Proposition

1. **Severe Documentation Burden & Clinician Burnout**
   - For every 1 hour spent in direct patient contact, physicians spend up to **2 additional hours** navigating electronic health records (EHR) and drafting clinical documentation.
   - Administrative overhead is a leading contributor to clinical exhaustion, reduced daily patient throughput, and high turnover rates across rural health units and private hospitals.

2. **The Regional Dialect & Code-Switching Barrier**
   - Mainstream ambient scribes (e.g., Nuance DAX, Abridge, Suki) are designed primarily for standardized English or Spanish.
   - In Philippine and Southeast Asian healthcare settings, consultations are characterized by rapid **code-switching** between regional dialects and national languages (*"Dok, kuminrot po an likod ko tatlong araw na, dai pa nin nainom na gamot"*).
   - Commercial speech recognition models frequently fail on localized medical idioms, confusing clinical intent and producing phonetically degraded transcripts.

3. **Hallucination Risk & Patient Safety**
   - Generic large language models (LLMs) frequently hallucinate unmentioned vital signs, fabricated prescriptions, or unwarranted diagnoses when prompted without constraints.
   - AuraScribe incorporates **strict clinical guardrails**: zero fabrication of vital signs, preservation of clinical contradictions, explicit flagging of uncorroborated diagnoses, and mandatory physician authorization.

4. **Interoperability & Data Portability**
   - Unstructured narrative notes in disparate doctor notebooks or PDF scans prevent systemic healthcare analytics.
   - AuraScribe outputs validated, strongly-typed JSON schemas ready for ingestion into modern hospital EMRs and PhilHealth reimbursement frameworks.

---

### 1.3 WHO: Target Beneficiaries & User Segments

| User Segment | Typical Setting | Core Value Realized |
| :--- | :--- | :--- |
| **Attending Clinicians & Specialists** | Private Outpatient Clinics & Hospitals | Reduces documentation time by 60–70%, enabling doctors to focus eye contact on patients rather than typing on a keyboard. |
| **Rural Health Units (RHU) & Municipal Doctors** | Provincial Health Centers & Barangay Health Stations | Accurately understands regional patient dialects (e.g. Bicolano, Tagalog) where patients struggle to explain complex pain in English. |
| **Dental & Surgical Practitioners** | Specialty Dental & Minor Surgery Suites | Hands-free, voice-driven capture during procedures using customizable specialty templates (e.g., Dental Exam Record). |
| **Healthcare System Administrators** | Hospital Networks & HMOs | Standardizes clinical record quality, shortens claim reimbursement cycles, and ensures legally defensible, physician-verified documentation. |
| **Patients** | Rural & Urban Consultation Rooms | Experience higher consultation satisfaction with clinicians who are fully engaged, listening, and responsive. |

---

### 1.4 HOW: Technical Architecture & Operating Mechanism

AuraScribe operates via a 5-tier modular processing pipeline:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   AURASCRIBE 5-TIER PIPELINE                                    │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
  1. AUDIO PRE-PROCESSING
     • Format standardization to 16kHz mono audio.
     • Spectral noise gating (via noisereduce & soundfile) to filter background air-conditioner hum,
       ceiling fans, static, and ambient room chatter.

  2. STT TRANSCRIPTION WITH REGIONAL BIASING
     • High-accuracy transcription using Whisper STT.
     • Dynamic vocabulary prompting (e.g., masakit, hilanat, alipunga, tyan, likod, nireseta,
       mabalos, maray, dai, iyo, tatlong araw, gamot).
     • Deterministic decoding (temperature=0.0) preventing phonetic mistranscription.

  3. LLM TRANSCRIPT CLEANING & ATTRIBUTION AGENT
     • Medical transcription editor prompt specialized for Philippine code-switching.
     • Phonetic error correction (e.g., "kumasakat" ➔ "masakit", "mahayin" ➔ "maray / salamat").
     • Eliminates filler particles ("po", "ano", "kuwan", "daa", "tabi") without altering clinical meaning.
     • Attributes speaker turns into structured dialogue ("Doctor: ..." vs "Patient: ...").

  4. STRUCTURED CLINICAL EXTRACTION & GUARDRAILS
     • Pydantic AI & OpenAI-compatible LLM extraction (supporting Groq 120B/27B, llama.cpp, Ollama).
     • Enforces strict SOAP schema typing (Subjective, Objective, Assessment, Plan).
     • Clinical safety guardrails: flags unverified impressions, enforces review_required=True.
     • Resilient fallback mechanism: direct JSON structured extraction prevents tool schema crashes.

  5. SCHEMA-DRIVEN, FORM-AGNOSTIC FRONTEND & SIGN-OFF
     • Dynamic UI generator rendering color-coded cards (Indigo, Teal, Blue, Purple).
     • Bidirectional data binding using dot-notation keys (data-key="subjective.chief_complaint").
     • Doctor review, inline modification, and one-click cryptographic "Approve & Sign Off".
```

---

## 2. Core Architectural Highlights

### 2.1 Schema-Driven, Form-Agnostic Engine
AuraScribe decouples the user interface from hardcoded fields. Form templates are stored as declarative JSON schemas under `templates/forms/` and `src/aurascribe/schemas/forms/`:
- **Standard SOAP Note (`soap_note.json`)**: General clinical medicine, internal medicine, outpatient consultations.
- **Dental Examination (`dental_exam.json`)**: Tooth quadrant, caries detection, periodontal status, procedures.
- **Triage & Emergency Record (`triage_record.json`)**: Acute acuity scoring, arrival vitals, rapid intervention.

When new specialty templates are registered on the backend, the client dynamically renders the required sections, inputs, textareas, and labels with **zero frontend redesign**.

### 2.2 Resilient Multi-Provider Backend
AuraScribe supports diverse inference backends, configurable dynamically via environment variables (`.env`):
- **Cloud Acceleration (Groq)**: Low-latency inference using `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`, and `whisper-large-v3-turbo`.
- **Local & On-Premise GPU (Ollama / llama.cpp)**: Zero-data-egress setup for strictly confidential or air-gapped hospital intranets.
- **Cloud Proprietary (OpenAI)**: Compatibility with GPT-4o, GPT-4o-mini, and standard Whisper APIs.

---

## 3. Strategic Future Product Roadmap

The following roadmap outlines the technical evolution, regulatory milestones, and clinical integrations planned for AuraScribe across five distinct execution phases.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              PRODUCT ROADMAP MILESTONES                                │
└────────────────────────────────────────────────────────────────────────────────────────┘
  Phase 1 (Q4 2026 - Q1 2027) ──► Phase 2 (Q2 2027) ──► Phase 3 (Q3 2027)
  Local Scribe & Diarization     Dialect Expansion     EHR & FHIR Interoperability
                                                                   │
  Phase 5 (2028+)             ◄── Phase 4 (Q4 2027)  ◄─────────────┘
  Ambient Intelligence & CDS      Compliance & RBAC
```

---

### Phase 1: Near-Term Infrastructure & Acoustic Enhancements
**Timeline:** Q4 2026 – Q1 2027  
**Strategic Focus:** Acoustic reliability, speaker diarization, and on-premise execution.

| Milestone | Objective | Technical Implementation |
| :--- | :--- | :--- |
| **1.1 On-Premise Whisper Inference** | Eliminate dependency on external cloud STT for facilities with sensitive health data. | Containerized `faster-whisper` and `vLLM` microservice running locally on Apple Silicon (MLX) or NVIDIA RTX/A-series GPUs. |
| **1.2 Acoustic Speaker Diarization** | Automatically distinguish between Doctor, Patient, and Accompanying Relative based on vocal timbre. | Integration of `pyannote.audio` diarization embeddings mapped directly into transcript turns. |
| **1.3 Interactive Audio-Transcript Sync** | Allow doctors to click any phrase in the transcript to jump playback to that exact audio timestamp. | Word-level timestamp extraction from Whisper `verbose_json` response bound to HTML5 audio playback. |
| **1.4 Clinical Form Marketplace** | Expand available specialty form schemas. | Schemas for Pediatrics, Obstetrics & Gynecology (OB-GYN), Dermatology, and Orthopedic clinics. |

---

### Phase 2: Regional Dialect & Edge Expansion
**Timeline:** Q2 2027  
**Strategic Focus:** Breadth of linguistic coverage and edge device performance.

| Milestone | Objective | Technical Implementation |
| :--- | :--- | :--- |
| **2.1 Philippine Dialect Expansion** | Expand vocabulary biasing and normalization beyond Tagalog and Bicolano. | Biasing dictionaries and evaluation sets for **Cebuano / Bisaya, Ilocano, Hiligaynon (Ilonggo), Waray, and Kapampangan**. |
| **2.2 Fine-Tuned Regional Clinical Adapters** | Increase accuracy for hyper-localized symptom descriptions. | Low-Rank Adaptation (LoRA) fine-tuning on sanitized bilingual clinical consultation dialogues. |
| **2.3 Offline Mobile PWA** | Enable provincial community health workers (BHWs) to record consultations in areas with zero internet. | Progressive Web App (PWA) with client-side IndexedDB audio queueing and auto-sync upon reconnection. |
| **2.4 Audio Noise Adaptive Filtering** | Improve noise suppression in open-air provincial clinics. | Real-time DeepFilterNet or RNNoise WASM audio preprocessing directly in the browser microphone stream. |

---

### Phase 3: Clinical EHR / EMR Interoperability & FHIR Standards
**Timeline:** Q3 2027  
**Strategic Focus:** Enterprise hospital integration and automated health insurance coding.

| Milestone | Objective | Technical Implementation |
| :--- | :--- | :--- |
| **3.1 HL7 FHIR v4 Resource Mapping** | Convert structured form extractions into standardized FHIR bundles. | Automated mapping to `Encounter`, `Condition`, `Observation`, `MedicationRequest`, and `Procedure` resources. |
| **3.2 PhilHealth Konsulta & E-Claims Integration** | Automate primary care encounter packaging for national healthcare reimbursement. | Automated ICD-10 diagnostic coding and Relative Value Scale (RVS) procedure code suggestion with physician confirmation. |
| **3.3 SMART-on-FHIR Embedded Launch** | Embed AuraScribe as a side-panel widget within existing Hospital Information Systems (HIS). | OAuth2 / OpenID Connect SMART launch flow supporting Epic, Cerner, Medtech, and bespoke Philippine hospital EMRs. |
| **3.4 Direct EHR Clipboard & Webhook Push** | Send signed notes directly into destination patient charts. | Webhook integration and HL7 MLLP feed dispatcher. |

---

### Phase 4: Enterprise Security, Governance & Regulatory Compliance
**Timeline:** Q4 2027  
**Strategic Focus:** Data privacy certifications, institutional access controls, and audit integrity.

| Milestone | Objective | Technical Implementation |
| :--- | :--- | :--- |
| **4.1 Philippine DPA & HIPAA Compliance** | Full legal and regulatory certification under Republic Act No. 10173 (Philippine Data Privacy Act of 2012) and HIPAA. | Implementation of end-to-end encryption at rest (AES-256) and in transit (TLS 1.3), complete de-identification, and BAA protocols. |
| **4.2 Role-Based Access Control (RBAC)** | Multi-tenant hospital support for clinics, departments, and medical residents. | Enterprise SSO (SAML 2.0 / Okta / Google Workspace), role tiers (Attending Physician, Resident, Scribe, Auditor). |
| **4.3 Cryptographic Audit Trail & E-Signatures** | Tamper-evident clinical note signing. | Public Key Infrastructure (PKI) digital signatures adhering to Philippine Electronic Commerce Act (RA 8792) standards. |
| **4.4 Automatic PHI Redaction** | Sanitize patient names, addresses, and phone numbers before LLM inference. | Named Entity Recognition (NER) pipeline stripping Protected Health Information prior to model ingestion. |

---

### Phase 5: Ambient Clinical Intelligence & Proactive Care
**Timeline:** 2028 and Beyond  
**Strategic Focus:** Ambient passive listening, real-time clinical safety alerts, and multilingual patient empowerment.

| Milestone | Objective | Technical Implementation |
| :--- | :--- | :--- |
| **5.1 Passive Ambient Exam Room Mode** | Continuous, hands-free consultation detection. | Hotword activation (*"AuraScribe start consultation"*) or acoustic voice activity detection (VAD) triggering automated intake. |
| **5.2 Real-Time Clinical Safety Intelligence** | Ambient clinical safety alerts delivered to the clinician during the encounter. | Cross-check prescribed drugs against reported patient allergies and current medications to flag contraindications instantly. |
| **5.3 Multilingual Patient Care Instructions** | Improve patient compliance and discharge comprehension. | Automatic synthesis of bilingual, patient-friendly aftercare instructions in the patient's spoken dialect (e.g., Central Bikol instructions for a Bikolano patient). |
| **5.4 Longitudinal Patient Encounter Tracking** | Contextual awareness of previous patient visits. | Vector database retrieval (RAG) providing brief summaries of past chief complaints and medication responses during the current consult. |

---

## 4. Key Performance Indicators (KPIs)

To evaluate clinical adoption and systemic efficacy, AuraScribe benchmarks progress against the following target metrics:

```
  ┌─────────────────────────┐    ┌─────────────────────────┐    ┌─────────────────────────┐
  │   DOCUMENTATION SPEED   │    │  TRANSCRIPTION FIDELITY │    │  ZERO-HALLUCINATION     │
  │   65% Reduction in Time │    │  < 8% WER on Dialects   │    │  0 Fabricated Vitals/Rx │
  └─────────────────────────┘    └─────────────────────────┘    └─────────────────────────┘
```

1. **Documentation Latency:** Average time required to complete, review, and sign off an encounter note reduced from **8.5 minutes** to **under 2 minutes**.
2. **Dialect Word Error Rate (WER):** Word Error Rate for Taglish and Bicolano consultation speech below **8%** across ambient clinic acoustic conditions.
3. **Clinical Safety & Zero Fabrication:** **100%** compliance with anti-hallucination guardrails; zero fabricated medications or vital signs permitted past validation.
4. **Physician Satisfaction (CSAT):** Greater than **90%** approval rating among participating doctors regarding UI simplicity and note accuracy.

---

## 5. Conclusion & Strategic Next Steps

AuraScribe bridges the critical divide between cutting-edge ambient artificial intelligence and the complex multilingual realities of Southeast Asian healthcare. By uniting **robust acoustic noise suppression**, **regional dialect biasing**, **zero-fabrication clinical guardrails**, and a **schema-driven, form-agnostic review interface**, AuraScribe returns clinicians' focus where it belongs: on the patient.

### Immediate Engineering Action Items
1. Maintain existing 100% test pass rate across all 68 schema, API, and agent test suites.
2. Complete containerized packaging for edge testing in provincial partner health clinics.
3. Begin dataset curation for Phase 2 regional dialect expansions (Cebuano and Ilocano biasing dictionaries).

---

*For inquiries, architectural reviews, or clinical pilot partnerships, please contact the AuraScribe Project Lead.*

