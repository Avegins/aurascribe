/**
 * AuraScribe Frontend Controller
 * Schema-Driven, Form-Agnostic UI for Multilingual Clinical Consultations.
 *
 * Implements:
 * 1. Audio recording & transcription ingestion
 * 2. Dialogue chat bubble rendering with highlighted clinical symptoms
 * 3. Dynamic schema-driven form rendering (Indigo, Teal, Blue, Purple cards)
 * 4. Bidirectional key mapping via data-key attributes
 * 5. Dynamic JSON copy & doctor sign-off authorization
 */

(function () {
    "use strict";

    // DOM Elements - Navigation & Header
    const consultDateDisplay = document.getElementById("consultDateDisplay");
    const consultLangDisplay = document.getElementById("consultLangDisplay");
    const btnHeaderCopyJson = document.getElementById("btnHeaderCopyJson");

    // DOM Elements - Recording & Controls
    const btnStart = document.getElementById("btnStart");
    const btnStop = document.getElementById("btnStop");
    const btnUpload = document.getElementById("btnUpload");
    const audioFileInput = document.getElementById("audioFileInput");
    const languageHintSelect = document.getElementById("languageHint");
    const formTypeSelect = document.getElementById("formTypeSelect");

    // DOM Elements - Status & Preview
    const statusDot = document.getElementById("statusDot");
    const statusText = document.getElementById("statusText");
    const recordingTimer = document.getElementById("recordingTimer");
    const audioPreviewContainer = document.getElementById("audioPreviewContainer");
    const audioPlayback = document.getElementById("audioPlayback");
    const audioInfoPill = document.getElementById("audioInfoPill");
    const audioPillTitle = document.getElementById("audioPillTitle");
    const audioPillDialect = document.getElementById("audioPillDialect");

    // DOM Elements - Alert Box
    const errorBox = document.getElementById("errorBox");
    const errorCategory = document.getElementById("errorCategory");
    const errorMessage = document.getElementById("errorMessage");

    // DOM Elements - Results Section
    const resultsSection = document.getElementById("resultsSection");
    const transcriptText = document.getElementById("transcriptText");
    const transcriptMeta = document.getElementById("transcriptMeta");
    const transcriptBubbleContainer = document.getElementById("transcriptBubbleContainer");

    // DOM Elements - Dynamic Form & Headers
    const formTitleHeader = document.getElementById("formTitleHeader");
    const formSubtitleHeader = document.getElementById("formSubtitleHeader");
    const reviewBadge = document.getElementById("reviewBadge");
    const btnCopyJson = document.getElementById("btnCopyJson");
    const btnToggleJson = document.getElementById("btnToggleJson");
    const btnCloseJsonDebug = document.getElementById("btnCloseJsonDebug");
    const jsonDebugSection = document.getElementById("jsonDebugSection");
    const soapJsonDisplay = document.getElementById("soapJsonDisplay");
    const warningsContainer = document.getElementById("warningsContainer");
    const warningsList = document.getElementById("warningsList");
    const dynamicFormContainer = document.getElementById("dynamicFormContainer");

    // State Variables
    let mediaRecorder = null;
    let audioChunks = [];
    let timerInterval = null;
    let recordingStartTime = null;
    let activeMimeType = "audio/webm";

    let currentFormSchema = null;
    let currentExtractedData = {};
    let currentRequestId = null;
    let lastTranscriptText = "";
    let lastDetectedLang = "auto";
    let isSignedOff = false;

    // Detect browser-supported audio recording MIME types
    function getSupportedMimeType() {
        const types = [
            "audio/webm;codecs=opus",
            "audio/webm",
            "audio/mp4",
            "audio/ogg;codecs=opus",
            "audio/wav"
        ];
        for (const t of types) {
            if (MediaRecorder.isTypeSupported(t)) {
                return t;
            }
        }
        return "audio/webm";
    }

    // Status helpers
    function setStatus(state, message) {
        statusDot.className = "status-dot " + state;
        statusText.textContent = message;
    }

    function clearError() {
        errorBox.style.display = "none";
        errorCategory.textContent = "";
        errorMessage.textContent = "";
    }

    function showError(category, msg) {
        setStatus("error", "Error encountered");
        errorBox.style.display = "flex";
        errorCategory.textContent = category || "Processing Error";
        errorMessage.textContent = msg || "An unexpected error occurred.";
    }

    // Timer helpers
    function startTimer() {
        recordingStartTime = Date.now();
        recordingTimer.style.display = "inline-block";
        recordingTimer.textContent = "00:00";
        timerInterval = setInterval(updateTimer, 500);
    }

    function stopTimer() {
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
    }

    function updateTimer() {
        const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
        const mins = String(Math.floor(elapsed / 60)).padStart(2, "0");
        const secs = String(elapsed % 60).padStart(2, "0");
        recordingTimer.textContent = `${mins}:${secs}`;
    }

    // Floating Toast Notification Helper
    function showToast(message, icon = "✓") {
        const existing = document.querySelector(".toast-notice");
        if (existing) existing.remove();

        const toast = document.createElement("div");
        toast.className = "toast-notice";
        toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transition = "opacity 0.4s ease";
            setTimeout(() => toast.remove(), 400);
        }, 2500);
    }

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Start Audio Recording
    async function startRecording() {
        clearError();
        audioChunks = [];

        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            showError("Browser Incompatible", "Microphone recording is not supported in this browser environment.");
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            activeMimeType = getSupportedMimeType();

            mediaRecorder = new MediaRecorder(stream, { mimeType: activeMimeType });

            mediaRecorder.ondataavailable = (event) => {
                if (event.data && event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = () => {
                stream.getTracks().forEach((track) => track.stop());
                const audioBlob = new Blob(audioChunks, { type: activeMimeType });

                const audioUrl = URL.createObjectURL(audioBlob);
                audioPlayback.src = audioUrl;
                audioPreviewContainer.style.display = "flex";

                if (audioInfoPill) {
                    audioInfoPill.style.display = "flex";
                    const durationStr = recordingTimer.textContent;
                    if (audioPillTitle) audioPillTitle.textContent = `Audio Recording (${durationStr})`;
                }

                submitAudioBlob(audioBlob, `recording.${activeMimeType.includes("mp4") ? "mp4" : "webm"}`);
            };

            mediaRecorder.start();
            btnStart.disabled = true;
            btnStop.disabled = false;
            btnUpload.disabled = true;
            audioFileInput.disabled = true;

            startTimer();
            setStatus("recording", "Recording consultation audio...");
        } catch (err) {
            console.error("Microphone access error:", err);
            showError("Permission Denied", "Unable to access microphone. Please ensure microphone permissions are granted.");
        }
    }

    // Stop Audio Recording
    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state !== "inactive") {
            mediaRecorder.stop();
            stopTimer();
            btnStart.disabled = false;
            btnStop.disabled = true;
            btnUpload.disabled = !audioFileInput.files.length;
            audioFileInput.disabled = false;
        }
    }

    // Submit Audio to API with progressive two-phase streaming
    async function submitAudioBlob(blob, filename) {
        clearError();
        isSignedOff = false;
        updateSignOffStatus(false);

        // Phase 1: Immediately reveal the results grid
        resultsSection.style.display = "grid";
        transcriptText.textContent = "🎧 Transcribing recorded consultation...";
        transcriptMeta.textContent = "Processing audio...";
        if (transcriptBubbleContainer) transcriptBubbleContainer.innerHTML = "";

        dynamicFormContainer.innerHTML = `
            <div class="empty-state" style="padding: 2.5rem; text-align: center; color: var(--text-muted);">
                <div class="status-dot processing" style="margin-bottom: 0.75rem; display: inline-block;"></div>
                <p>🎧 Transcribing recorded conversation...</p>
            </div>
        `;
        soapJsonDisplay.textContent = "⏳ Transcribing recorded conversation...";
        warningsContainer.style.display = "none";
        setStatus("processing", "Transcribing consultation audio...");

        const formData = new FormData();
        formData.append("audio", blob, filename);

        const langHint = languageHintSelect.value;
        if (langHint) {
            formData.append("language_hint", langHint);
        }

        const selectedFormType = formTypeSelect ? formTypeSelect.value : "soap_note";
        formData.append("form_type", selectedFormType);

        let transcriptData = null;

        try {
            const transResponse = await fetch("/api/transcribe", {
                method: "POST",
                body: formData,
            });

            const transJson = await transResponse.json();

            if (!transResponse.ok) {
                const errCat = transJson.error ? transJson.error.category : "Transcription Failed";
                const errMsg = transJson.error ? transJson.error.message : `HTTP error ${transResponse.status}`;
                showError(errCat, errMsg);
                resultsSection.style.display = "none";
                setStatus("error", "Transcription failed.");
                return;
            }

            transcriptData = transJson.transcript || {};
            lastTranscriptText = transcriptData.text || "";
            transcriptText.textContent = lastTranscriptText || "No transcript returned.";

            const meta = transcriptData.metadata || {};
            const lang = meta.detected_language || "N/A";
            lastDetectedLang = lang;
            const duration = meta.duration_seconds ? `${meta.duration_seconds.toFixed(1)}s` : "";
            transcriptMeta.textContent = `Language: ${lang} ${duration ? "• " + duration : ""}`;

            if (consultLangDisplay) {
                consultLangDisplay.textContent = lang === "tl" ? "Tagalog / Taglish" : (lang === "bcl" ? "Bicolano Dialect" : lang.toUpperCase());
            }

            // Render interim dialogue bubbles
            renderDialogueBubbles(lastTranscriptText);

        } catch (err) {
            console.error("Transcription network error:", err);
            showError("Network Error", "Failed to connect to transcription service.");
            resultsSection.style.display = "none";
            return;
        }

        // Phase 2: Run clinical extraction and render dynamic form
        await runClinicalExtraction(lastTranscriptText, lastDetectedLang, selectedFormType);
    }

    // Step 2 sub-routine: Extract clinical facts into schema-driven form
    async function runClinicalExtraction(transcriptTextContent, detectedLang, formType = "soap_note") {
        setStatus("processing", "🧠 Analyzing conversation and preparing clinical note...");

        dynamicFormContainer.innerHTML = `
            <div class="empty-state" style="padding: 2.5rem; text-align: center; color: var(--text-muted);">
                <div class="status-dot processing" style="margin-bottom: 0.75rem; display: inline-block;"></div>
                <p>🧠 Generating clinical consultation note...</p>
                <span style="font-size: 0.8rem; color: #94a3b8;">Structuring findings into review form</span>
            </div>
        `;

        try {
            const extractResponse = await fetch("/api/extract", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    text: transcriptTextContent,
                    language: detectedLang || "auto",
                    form_type: formType,
                }),
            });

            const extractJson = await extractResponse.json();

            if (!extractResponse.ok) {
                const errCat = extractJson.error ? extractJson.error.category : "Unable to Generate Note";
                const errMsg = extractJson.error ? extractJson.error.message : `HTTP error ${extractResponse.status}`;

                dynamicFormContainer.innerHTML = `
                    <div class="alert-box alert-error">
                        <span class="alert-icon">⚠️</span>
                        <div class="alert-content">
                            <strong>Unable to Generate Note:</strong>
                            <p>${escapeHtml(errMsg)}</p>
                        </div>
                    </div>
                `;

                soapJsonDisplay.textContent = `⚠️ Unable to generate note: ${errMsg}\n\nPlease check your server or connection and try again.`;
                showError(errCat, errMsg);
                setStatus("error", "Unable to Generate Note.");
                return;
            }

            currentRequestId = extractJson.request_id || null;
            const cleanedTranscript = extractJson.cleaned_transcript || transcriptTextContent;

            // Re-render conversation dialogue bubbles with cleaned speaker turns
            renderDialogueBubbles(cleanedTranscript);

            // Render Validation Warnings
            const warnings = extractJson.validation_warnings || [];
            if (warnings.length > 0) {
                warningsList.innerHTML = "";
                warnings.forEach((w) => {
                    const li = document.createElement("li");
                    li.textContent = w;
                    warningsList.appendChild(li);
                });
                warningsContainer.style.display = "block";
            } else {
                warningsContainer.style.display = "none";
            }

            // Bind schema & extracted data
            currentFormSchema = extractJson.form_schema || null;
            currentExtractedData = extractJson.extracted_data || extractJson.soap_note || {};

            // Render the Dynamic, Schema-Driven Form
            renderDynamicForm(currentFormSchema, currentExtractedData);

            // Sync raw JSON for debug viewer
            soapJsonDisplay.textContent = JSON.stringify(extractJson.soap_note || currentExtractedData, null, 2);

            setStatus("completed", "Consultation note generated and ready for doctor review.");

        } catch (err) {
            console.error("Clinical extraction network error:", err);
            dynamicFormContainer.innerHTML = `<div class="alert-box alert-error"><p>Unable to generate note: ${escapeHtml(err.message)}</p></div>`;
            showError("Network Error", "Failed to connect to extraction endpoint.");
            setStatus("error", "Unable to Generate Note.");
        }
    }

    // ==============================================================================
    // DYNAMIC FORM RENDERER (SCHEMA-DRIVEN & FORM-AGNOSTIC)
    // ==============================================================================
    function renderDynamicForm(schema, extractedData) {
        if (!dynamicFormContainer) return;
        dynamicFormContainer.innerHTML = "";

        if (!schema || !schema.sections) {
            dynamicFormContainer.innerHTML = `
                <div class="empty-state" style="padding: 2rem; text-align: center;">
                    <p>No valid form schema found.</p>
                </div>
            `;
            return;
        }

        // Update card header titles
        if (formTitleHeader && schema.form_title) {
            formTitleHeader.textContent = schema.form_title;
        }
        if (formSubtitleHeader && schema.form_description) {
            formSubtitleHeader.textContent = schema.form_description;
        }

        // Render each Section Card
        schema.sections.forEach((section) => {
            const theme = section.color_theme || "indigo";
            const badgeText = section.badge || (section.id ? section.id.charAt(0).toUpperCase() : "•");

            const sectionCard = document.createElement("div");
            sectionCard.className = `dynamic-section-card theme-${theme}`;
            sectionCard.id = `section-${section.id}`;

            // Section Header
            const header = document.createElement("div");
            header.className = "section-card-header";
            header.innerHTML = `
                <div class="section-title-group">
                    <div style="display: flex; align-items: center; gap: 0.6rem;">
                        <span class="section-badge badge-${theme}">${escapeHtml(badgeText)}</span>
                        <h4 class="section-title">${escapeHtml(section.title)}</h4>
                    </div>
                    ${section.subtitle ? `<span class="section-subtitle">${escapeHtml(section.subtitle)}</span>` : ""}
                </div>
            `;
            sectionCard.appendChild(header);

            // Section Body & Fields Grid
            const body = document.createElement("div");
            body.className = "section-card-body";

            const fieldsGrid = document.createElement("div");
            fieldsGrid.className = "fields-grid";

            section.fields.forEach((field) => {
                const fieldWrapper = document.createElement("div");
                const colClass = field.grid_column ? "col-span-1" : "col-full";
                fieldWrapper.className = `field-group ${colClass}`;

                // Value mapping using dot notation and clinical aliases
                const val = getValueByPath(extractedData, field.key);

                const label = document.createElement("label");
                label.className = "field-label";
                label.htmlFor = `field_${field.key.replace(/\./g, "_")}`;
                label.innerHTML = `${escapeHtml(field.label)} ${field.required ? '<span class="required-star">*</span>' : ""}`;
                fieldWrapper.appendChild(label);

                let inputEl;
                if (field.type === "textarea") {
                    inputEl = document.createElement("textarea");
                    inputEl.className = "form-control form-textarea";
                    inputEl.rows = field.rows || 3;
                } else {
                    inputEl = document.createElement("input");
                    inputEl.type = field.type || "text";
                    inputEl.className = "form-control form-input";
                }

                inputEl.id = `field_${field.key.replace(/\./g, "_")}`;
                inputEl.setAttribute("data-key", field.key);
                inputEl.placeholder = field.placeholder || "";
                inputEl.value = val || "";
                if (field.required) {
                    inputEl.required = true;
                }

                // Interactive modification listener
                inputEl.addEventListener("input", () => {
                    inputEl.classList.add("user-modified");
                    if (isSignedOff) {
                        updateSignOffStatus(false);
                    }
                });

                fieldWrapper.appendChild(inputEl);
                fieldsGrid.appendChild(fieldWrapper);
            });

            body.appendChild(fieldsGrid);
            sectionCard.appendChild(body);
            dynamicFormContainer.appendChild(sectionCard);
        });

        // Add Bottom Action Bar
        const actionsBar = document.createElement("div");
        actionsBar.className = "form-actions-bar";
        actionsBar.innerHTML = `
            <div class="actions-left">
                <button type="button" id="btnRerunExtraction" class="btn btn-outline btn-sm">
                    <span class="icon">🔄</span> Re-run Analysis
                </button>
            </div>
            <div class="actions-right">
                <button type="button" id="btnSignOff" class="btn btn-success">
                    <span class="icon">✍️</span> Approve &amp; Sign Off
                </button>
            </div>
        `;
        dynamicFormContainer.appendChild(actionsBar);

        // Bind Action Handlers
        const btnRerun = document.getElementById("btnRerunExtraction");
        const btnSign = document.getElementById("btnSignOff");

        if (btnRerun) btnRerun.addEventListener("click", onRerunExtraction);
        if (btnSign) btnSign.addEventListener("click", onSignOff);
    }

    // ==============================================================================
    // DOT NOTATION RESOLUTION & BIDIRECTIONAL DATA SCRAPING
    // ==============================================================================
    function getValueByPath(obj, path) {
        if (!obj || !path) return "";

        // 1. Exact path lookup
        const parts = path.split(".");
        let current = obj;
        let found = true;
        for (const p of parts) {
            if (current === null || current === undefined) {
                found = false;
                break;
            }
            current = current[p];
        }

        if (found && current !== undefined && current !== null) {
            return formatValueToString(current);
        }

        // 2. Clinical Aliases Fallback mapping
        const ALIASES = {
            "subjective.history_of_present_illness": ["subjective.history", "subjective.hpi", "history"],
            "subjective.history": ["subjective.history_of_present_illness", "history"],
            "subjective.chief_complaint": ["chief_complaint", "subjective.complaint"],
            "subjective.current_medications": ["subjective.medications", "plan.medications", "current_medications"],
            "subjective.allergies": ["allergies", "subjective.allergy"],
            "objective.vital_signs": ["objective.vitals", "vital_signs", "vitals"],
            "objective.physical_exam": ["objective.examination_findings", "examination_findings", "physical_exam"],
            "assessment.primary_diagnosis": ["assessment.clinical_impression", "clinical_impression", "diagnosis"],
            "assessment.differential_diagnoses": ["assessment.uncertainties", "differential_diagnoses", "differential"],
            "plan.prescriptions": ["plan.medications", "medications", "prescriptions"],
            "plan.instructions": ["plan.treatment", "treatment", "instructions", "plan.follow_up", "follow_up"],
        };

        const fallbacks = ALIASES[path] || [];
        for (const altPath of fallbacks) {
            const altParts = altPath.split(".");
            let altCurrent = obj;
            let altFound = true;
            for (const ap of altParts) {
                if (altCurrent === null || altCurrent === undefined) {
                    altFound = false;
                    break;
                }
                altCurrent = altCurrent[ap];
            }
            if (altFound && altCurrent !== undefined && altCurrent !== null && altCurrent !== "") {
                return formatValueToString(altCurrent);
            }
        }

        return "";
    }

    function formatValueToString(val) {
        if (typeof val === "string") return val.trim();
        if (typeof val === "number" || typeof val === "boolean") return String(val);

        if (Array.isArray(val)) {
            if (val.length === 0) return "";
            return val
                .map((item) => {
                    if (typeof item === "object" && item !== null) {
                        return Object.entries(item)
                            .filter(([_, v]) => v)
                            .map(([k, v]) => `${k}: ${v}`)
                            .join(", ");
                    }
                    return String(item);
                })
                .join("\n");
        }

        if (typeof val === "object" && val !== null) {
            return Object.entries(val)
                .filter(([_, v]) => v)
                .map(([k, v]) => `${k.replace(/_/g, " ").toUpperCase()}: ${v}`)
                .join(", ");
        }

        return "";
    }

    // Scrapes dynamic form data using data-key attributes into structured JSON
    function getFormData(container) {
        if (!container) return {};
        const data = {};
        const inputs = container.querySelectorAll("[data-key]");

        inputs.forEach((el) => {
            const key = el.getAttribute("data-key");
            if (!key) return;
            const value = el.value !== undefined ? el.value.trim() : "";

            const parts = key.split(".");
            let current = data;
            for (let i = 0; i < parts.length - 1; i++) {
                const part = parts[i];
                if (!current[part] || typeof current[part] !== "object") {
                    current[part] = {};
                }
                current = current[part];
            }
            current[parts[parts.length - 1]] = value;
        });

        return data;
    }

    // ==============================================================================
    // ACTION HANDLERS: COPY JSON, SIGN OFF, RERUN EXTRACTION
    // ==============================================================================
    async function onCopyJson() {
        const formData = getFormData(dynamicFormContainer);
        const jsonString = JSON.stringify(formData, null, 2);

        try {
            await navigator.clipboard.writeText(jsonString);
            showToast("Clinical JSON copied to clipboard!", "📋");

            // Temporary visual indicator on buttons
            [btnCopyJson, btnHeaderCopyJson].forEach((btn) => {
                if (!btn) return;
                const orig = btn.innerHTML;
                btn.innerHTML = `✓ Copied!`;
                setTimeout(() => (btn.innerHTML = orig), 2000);
            });
        } catch (err) {
            console.error("Copy JSON error:", err);
            showToast("Failed to copy JSON to clipboard.", "❌");
        }
    }

    async function onSignOff() {
        const formData = getFormData(dynamicFormContainer);
        const formType = formTypeSelect ? formTypeSelect.value : "soap_note";

        setStatus("processing", "Authorizing clinical documentation...");

        try {
            const response = await fetch("/api/sign-off", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    request_id: currentRequestId,
                    form_type: formType,
                    form_data: formData,
                    physician_name: "Dr. Avegin Manaog, MD",
                    license_number: "PRC-MED-2026-90482",
                }),
            });

            const resJson = await response.json();

            if (response.ok && resJson.signed_off) {
                isSignedOff = true;
                updateSignOffStatus(true, resJson.physician ? resJson.physician.name : "Dr. Avegin Manaog, MD");
                showToast("Documentation successfully signed off and verified!", "✍️");
                setStatus("completed", "Signed and verified by attending physician.");
            } else {
                showToast("Sign off authorization failed.", "❌");
                setStatus("error", "Sign off failed.");
            }
        } catch (err) {
            console.error("Sign off network error:", err);
            showToast("Error connecting to sign-off service.", "❌");
            setStatus("error", "Sign off network error.");
        }
    }

    function updateSignOffStatus(signed, physicianName = "Dr. Avegin Manaog, MD") {
        const btnSign = document.getElementById("btnSignOff");
        if (signed) {
            if (reviewBadge) {
                reviewBadge.className = "badge badge-success";
                reviewBadge.style.background = "#dcfce7";
                reviewBadge.style.color = "#15803d";
                reviewBadge.style.border = "1px solid #86efac";
                reviewBadge.innerHTML = `✓ Verified &amp; Signed by ${escapeHtml(physicianName)}`;
            }
            if (btnSign) {
                btnSign.classList.add("signed");
                btnSign.innerHTML = `✓ Verified &amp; Signed Off`;
            }
        } else {
            if (reviewBadge) {
                reviewBadge.className = "badge badge-warning";
                reviewBadge.style.background = "";
                reviewBadge.style.color = "";
                reviewBadge.style.border = "";
                reviewBadge.textContent = "Review Required";
            }
            if (btnSign) {
                btnSign.classList.remove("signed");
                btnSign.innerHTML = `<span class="icon">✍️</span> Approve &amp; Sign Off`;
            }
        }
    }

    function onRerunExtraction() {
        if (!lastTranscriptText) {
            showToast("No consultation transcript available to extract.", "⚠️");
            return;
        }
        const selectedFormType = formTypeSelect ? formTypeSelect.value : "soap_note";
        runClinicalExtraction(lastTranscriptText, lastDetectedLang, selectedFormType);
    }

    // ==============================================================================
    // CONVERSATIONAL CHAT BUBBLE RENDERER (SPEAKER ATTRIBUTION & HIGHLIGHTS)
    // ==============================================================================
    function renderDialogueBubbles(transcript) {
        if (!transcriptBubbleContainer) return;
        transcriptBubbleContainer.innerHTML = "";

        if (!transcript || !transcript.trim()) return;

        // Split by lines or speaker turns
        const lines = transcript.split("\n").filter((l) => l.trim().length > 0);

        // Clinical keywords to subtly highlight
        const SYMPTOM_PATTERNS = [
            /masakit ang likod(?: ko)?/gi,
            /masakit/gi,
            /kumikirot/gi,
            /tatlong araw(?: na)?/gi,
            /wala(?: pa)? naman(?: po)? akong iniinom na gamot/gi,
            /gamot/gi,
            /lagnat/gi,
            /hilanat/gi,
            /ubo/gi,
            /alipunga/gi,
            /tyan/gi,
            /likod/gi,
            /sakit/gi,
            /pulpitis/gi,
            /ngipin/gi,
        ];

        function highlightKeywords(text) {
            let processed = escapeHtml(text);
            SYMPTOM_PATTERNS.forEach((pattern) => {
                processed = processed.replace(pattern, (match) => `<mark class="highlight-symptom">${match}</mark>`);
            });
            return processed;
        }

        let timeOffset = 2;

        lines.forEach((line) => {
            const trimmed = line.trim();
            const doctorMatch = trimmed.match(/^(?:Doctor|\*\*Doctor\*\*|Dok|Doc)\s*:\s*(.+)$/i);
            const patientMatch = trimmed.match(/^(?:Patient|\*\*Patient\*\*|Pasyente)\s*:\s*(.+)$/i);

            const bubble = document.createElement("div");
            const timeStr = `00:${String(timeOffset).padStart(2, "0")}`;
            timeOffset += 4;

            if (doctorMatch) {
                bubble.className = "chat-bubble bubble-doctor";
                bubble.innerHTML = `
                    <div class="chat-bubble-header">
                        <span class="bubble-badge bubble-badge-doctor">Doctor</span>
                        <span class="bubble-timestamp">${timeStr}</span>
                    </div>
                    <div class="bubble-text">${highlightKeywords(doctorMatch[1])}</div>
                `;
            } else if (patientMatch) {
                bubble.className = "chat-bubble bubble-patient";
                bubble.innerHTML = `
                    <div class="chat-bubble-header">
                        <span class="bubble-badge bubble-badge-patient">Patient</span>
                        <span class="bubble-timestamp">${timeStr}</span>
                    </div>
                    <div class="bubble-text">${highlightKeywords(patientMatch[1])}</div>
                `;
            } else {
                // Generic turn
                bubble.className = "chat-bubble bubble-doctor";
                bubble.innerHTML = `
                    <div class="chat-bubble-header">
                        <span class="bubble-badge bubble-badge-doctor">Dialogue</span>
                        <span class="bubble-timestamp">${timeStr}</span>
                    </div>
                    <div class="bubble-text">${highlightKeywords(trimmed)}</div>
                `;
            }

            transcriptBubbleContainer.appendChild(bubble);
        });
    }

    // ==============================================================================
    // EVENT LISTENERS & INITIALIZATION
    // ==============================================================================
    btnStart.addEventListener("click", startRecording);
    btnStop.addEventListener("click", stopRecording);

    audioFileInput.addEventListener("change", () => {
        btnUpload.disabled = !audioFileInput.files.length;
        if (audioFileInput.files.length) {
            const file = audioFileInput.files[0];
            audioPlayback.src = URL.createObjectURL(file);
            audioPreviewContainer.style.display = "flex";
            if (audioInfoPill) {
                audioInfoPill.style.display = "flex";
                if (audioPillTitle) audioPillTitle.textContent = `Audio File (${file.name})`;
            }
        }
    });

    btnUpload.addEventListener("click", () => {
        if (audioFileInput.files.length) {
            const file = audioFileInput.files[0];
            submitAudioBlob(file, file.name);
        }
    });

    // Copy JSON handlers (if present)
    if (btnCopyJson) btnCopyJson.addEventListener("click", onCopyJson);
    if (btnHeaderCopyJson) btnHeaderCopyJson.addEventListener("click", onCopyJson);

    // Dynamic Form Template Switcher
    if (formTypeSelect) {
        formTypeSelect.addEventListener("change", async () => {
            const selectedType = formTypeSelect.value;
            try {
                const res = await fetch(`/api/forms/${selectedType}`);
                const data = await res.json();
                if (data.form_schema) {
                    currentFormSchema = data.form_schema;
                    renderDynamicForm(currentFormSchema, currentExtractedData);
                    showToast(`Switched to template: ${currentFormSchema.form_title}`, "📑");
                }
            } catch (err) {
                console.error("Error switching form schema:", err);
            }
        });
    }

    // Set today's consultation date
    if (consultDateDisplay) {
        const today = new Date();
        consultDateDisplay.textContent = today.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric"
        });
    }
})();
