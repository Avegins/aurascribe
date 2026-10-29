# AuraScribe Documentation Hub 📚

Welcome to the documentation suite for **AuraScribe**, the ambient clinical intelligence and multilingual documentation aid for Philippine and global healthcare.

---

## Documents Directory

| Document | Purpose | Target Audience |
| :--- | :--- | :--- |
| **[Project Structure & Architecture](PROJECT_STRUCTURE.md)** | **Complete codebase ownership guide:** explains every module, file, data flow, dynamic schema engine, and extension recipes. | Codebase Owners, Full-Stack Engineers, AI Engineers |
| **[Executive Summary](EXECUTIVE_SUMMARY.md)** | Answers the core **What, Why, Who, and How** of the project, including clinical rationale, core technical architecture, and high-level roadmap. | Clinical Leaders, Healthcare Administrators, Investors, Engineering Stakeholders |
| **[Technical Product Roadmap](ROADMAP.md)** | Comprehensive 5-phase engineering roadmap with detailed milestones, acceptance criteria, and architecture evolution targets. | Full-Stack Engineers, AI Engineers, Product Managers, Clinical Informaticists |

---

## Quick Navigation

- **What AuraScribe Does:** Converts recorded doctor-patient consultations (Tagalog, Taglish, Bicolano dialects, English) into verified, structured SOAP notes and clinical records.
- **Why It Matters:** Eliminates 60–70% of clinical administrative documentation time and bridges the regional dialect barrier with zero-hallucination guardrails.
- **How It Operates:** A 6-stage pipeline featuring noise reduction, Whisper dialect biasing (`temperature=0.0`), LLM transcript cleaning, structured clinical extraction, safety guardrails, and dynamic schema binding with physician sign-off.

---

*For setup and local development instructions, see the main [README.md](../README.md).*
