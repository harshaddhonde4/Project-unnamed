// Global State
let ws = null;
let allCallLogs = [];
let allRoster = [];
let activeTimer = null;
let callStartTime = null;

// Speech Synthesis & Recognition for In-Browser Softphone
let speechSynth = window.speechSynthesis;
let speechRecognizer = null;
let isMicListening = false;
let currentBrowserCall = null;

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
    initWebSocket();
    initSpeechRecognition();
    fetchStats();
    fetchCallLogs();
    fetchRoster();
    loadSettings();
    lucide.createIcons();
});

// WebSocket Handler
function initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        const pill = document.getElementById("wsStatusPill");
        if (pill) {
            pill.className = "flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
            document.getElementById("wsPing").className = "animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75";
            document.getElementById("wsDot").className = "relative inline-flex rounded-full h-2 w-2 bg-emerald-500";
            document.getElementById("wsStatusText").innerText = "Live Connected";
        }
    };

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleWsMessage(msg);
        } catch (e) {
            console.error("WS Parse error:", e);
        }
    };

    ws.onclose = () => {
        const pill = document.getElementById("wsStatusPill");
        if (pill) {
            pill.className = "flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20";
            document.getElementById("wsPing").className = "hidden";
            document.getElementById("wsDot").className = "relative inline-flex rounded-full h-2 w-2 bg-rose-500";
            document.getElementById("wsStatusText").innerText = "Reconnecting...";
        }
        setTimeout(initWebSocket, 3000);
    };
}

function handleWsMessage(msg) {
    if (msg.type === "STATS_UPDATE") {
        renderStats(msg.data);
    } else if (msg.type === "CALL_EVENT") {
        updateActiveCallBanner(msg);
    } else if (msg.type === "CALL_COMPLETED") {
        handleCallCompleted(msg);
    } else if (msg.type === "CAMPAIGN_STARTED") {
        showCampaignProgress(0, msg.total);
    } else if (msg.type === "CAMPAIGN_PROGRESS") {
        showCampaignProgress(msg.current, msg.total, msg.student_name);
    } else if (msg.type === "CAMPAIGN_FINISHED" || msg.type === "CAMPAIGN_STOPPED") {
        hideCampaignProgress();
        fetchStats();
        fetchCallLogs();
    } else if (msg.type === "BROWSER_CALL_INCOMING") {
        startBrowserInteractiveSession(msg);
    }
}

// ----------------- Speech Recognition & Softphone -----------------
function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        speechRecognizer = new SpeechRecognition();
        speechRecognizer.continuous = false;
        speechRecognizer.interimResults = true;
        speechRecognizer.lang = "en-IN"; // English (India) or default

        speechRecognizer.onstart = () => {
            isMicListening = true;
            updateMicButtonUI(true);
        };

        speechRecognizer.onresult = (event) => {
            let transcript = "";
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                transcript += event.results[i][0].transcript;
            }
            document.getElementById("spUserSpeech").innerHTML = `<span class="text-white font-bold">"${transcript}"</span>`;
            document.getElementById("liveTranscriptText").innerHTML = `<span class="text-white">You: "${transcript}"</span>`;

            if (event.results[0].isFinal) {
                handleUserFinalSpeech(transcript);
            }
        };

        speechRecognizer.onerror = (event) => {
            console.warn("Speech recognition error:", event.error);
            isMicListening = false;
            updateMicButtonUI(false);
        };

        speechRecognizer.onend = () => {
            isMicListening = false;
            updateMicButtonUI(false);
        };
    } else {
        console.warn("Web Speech API Recognition not supported in this browser.");
    }
}

function speakText(text, onCompleteCallback) {
    if (!speechSynth) {
        if (onCompleteCallback) onCompleteCallback();
        return;
    }
    speechSynth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    
    // Pick an Indian English voice if available
    const voices = speechSynth.getVoices();
    const indianVoice = voices.find(v => v.lang.includes("en-IN") || v.name.includes("India") || v.name.includes("Aditi"));
    if (indianVoice) {
        utterance.voice = indianVoice;
    }

    utterance.onend = () => {
        if (onCompleteCallback) onCompleteCallback();
    };
    utterance.onerror = () => {
        if (onCompleteCallback) onCompleteCallback();
    };

    speechSynth.speak(utterance);
}

// Start Live Browser Demo using Laptop Microphone
function startBrowserInteractiveDemo() {
    // Pick first student from roster or default
    const student = allRoster.length > 0 ? allRoster[0] : {
        student_name: "Aarav Sharma",
        parent_name: "Rajesh Sharma",
        mobile_number: "+919876543210",
        pending_amount: 18500.0,
        due_date: "2026-10-15",
        institute_name: "Apex Learning Academy"
    };

    dialSingleStudent(
        student.student_name,
        student.parent_name,
        student.mobile_number,
        student.pending_amount,
        student.due_date
    );
}

function startBrowserInteractiveSession(session) {
    currentBrowserCall = session;
    document.getElementById("spRecipientName").innerText = `Calling ${session.parent_name || session.student_name}`;
    document.getElementById("spFeeDuesText").innerText = `Pending: ₹${Math.round(session.amount).toLocaleString("en-IN")} for ${session.student_name} (Due: ${session.due_date})`;
    document.getElementById("spCallStateBadge").className = "inline-block mt-2 px-3 py-0.5 rounded-full text-xs font-semibold bg-sky-500/20 text-sky-400 border border-sky-500/30";
    document.getElementById("spCallStateBadge").innerText = "BOT IS SPEAKING 🤖";
    document.getElementById("spBotSpeech").innerText = `"${session.prompt_text}"`;
    document.getElementById("spUserSpeech").innerHTML = `<span class="text-slate-500 italic">Please listen to the bot first... microphone will open in a moment.</span>`;

    openModal("softphoneModal");

    // Also update main banner
    updateActiveCallBanner({
        student_name: session.student_name,
        phone: session.phone,
        status: "IN_PROGRESS",
        step: "In-Browser Call connected! Bot speaking aloud...",
        transcript: session.prompt_text
    });

    // Speak aloud through speaker
    speakText(session.prompt_text, () => {
        // Once bot finishes, open microphone
        document.getElementById("spCallStateBadge").className = "inline-block mt-2 px-3 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 animate-pulse";
        document.getElementById("spCallStateBadge").innerText = "LISTENING TO YOUR MIC 🎙️";
        document.getElementById("spUserSpeech").innerHTML = `<span class="text-emerald-400 font-semibold">Microphone active! Speak now (e.g. "I already paid yesterday" or "I will pay next Monday on 10th").</span>`;
        startMicRecording();
    });
}

function startMicRecording() {
    if (speechRecognizer && !isMicListening) {
        try {
            speechRecognizer.start();
        } catch (e) {
            console.warn("Could not start recognizer:", e);
        }
    }
}

function toggleMicRecording() {
    if (isMicListening) {
        speechRecognizer.stop();
    } else {
        startMicRecording();
    }
}

function updateMicButtonUI(listening) {
    const btn = document.getElementById("spMicToggleBtn");
    const txt = document.getElementById("spMicBtnText");
    if (listening) {
        btn.className = "flex items-center space-x-2 px-5 py-2.5 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition shadow-lg shadow-emerald-600/20 animate-pulse";
        txt.innerText = "Listening to Mic...";
    } else {
        btn.className = "flex items-center space-x-2 px-5 py-2.5 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 transition";
        txt.innerText = "Click to Speak";
    }
}

async function handleUserFinalSpeech(spokenText) {
    if (!currentBrowserCall) return;

    document.getElementById("spCallStateBadge").className = "inline-block mt-2 px-3 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-400 border border-indigo-500/30";
    document.getElementById("spCallStateBadge").innerText = "ANALYZING YOUR INTENT 🧠";

    updateActiveCallBanner({
        student_name: currentBrowserCall.student_name,
        phone: currentBrowserCall.phone,
        status: "SPEECH_RECOGNITION",
        step: "Processing your spoken speech...",
        transcript: `You: "${spokenText}"`
    });

    try {
        const res = await fetch("/api/call/browser-response", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                call_uuid: currentBrowserCall.call_uuid,
                student_name: currentBrowserCall.student_name,
                pending_amount: currentBrowserCall.amount,
                speech_text: spokenText,
                duration: 25
            })
        });
        const data = await res.json();
        
        // Bot responds aloud to user
        document.getElementById("spBotSpeech").innerText = `"${data.bot_reply}"`;
        document.getElementById("spCallStateBadge").innerText = `EXTRACTED: ${data.outcome} ✅`;

        speakText(data.bot_reply, () => {
            setTimeout(() => {
                closeModal("softphoneModal");
                currentBrowserCall = null;
            }, 2500);
        });

    } catch (e) {
        alert("Error analyzing response: " + e.message);
    }
}

function hangupSoftphone() {
    if (speechSynth) speechSynth.cancel();
    if (speechRecognizer && isMicListening) speechRecognizer.stop();
    closeModal("softphoneModal");
    currentBrowserCall = null;
}

// ----------------- Active Call Banner & Events -----------------
function updateActiveCallBanner(event) {
    const student = document.getElementById("liveCallStudent");
    const phone = document.getElementById("liveCallPhone");
    const badge = document.getElementById("liveCallStatusBadge");
    const transcript = document.getElementById("liveTranscriptText");
    const wave = document.getElementById("soundwaveContainer");

    student.innerText = `Calling ${event.student_name || "Student"}`;
    phone.innerText = `Recipient: ${event.phone || "-"} • ${event.step || ""}`;

    if (event.status === "DIALING") {
        badge.className = "px-2.5 py-0.5 rounded-full text-xs font-medium bg-sky-500/20 text-sky-400 border border-sky-500/30 animate-pulse";
        badge.innerText = "DIALING 📞";
        wave.classList.add("hidden");
    } else if (event.status === "RINGING") {
        badge.className = "px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/20 text-amber-400 border border-amber-500/30 animate-pulse";
        badge.innerText = "RINGING 🔔";
        wave.classList.add("hidden");
    } else if (event.status === "IN_PROGRESS" || event.status === "SPEECH_RECOGNITION") {
        badge.className = "px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
        badge.innerText = event.status === "SPEECH_RECOGNITION" ? "LISTENING 🗣️" : "SPEAKING 🤖";
        wave.classList.remove("hidden");
    }

    if (event.transcript) {
        transcript.innerHTML = `<span class="text-white">${event.transcript}</span>`;
    }

    if (!callStartTime) {
        callStartTime = Date.now();
        activeTimer = setInterval(updateTimerDisplay, 1000);
    }
}

function handleCallCompleted(msg) {
    const student = document.getElementById("liveCallStudent");
    const phone = document.getElementById("liveCallPhone");
    const badge = document.getElementById("liveCallStatusBadge");
    const transcript = document.getElementById("liveTranscriptText");
    const wave = document.getElementById("soundwaveContainer");

    wave.classList.add("hidden");
    clearInterval(activeTimer);
    callStartTime = null;

    badge.className = "px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-500/20 text-indigo-400 border border-indigo-500/30";
    badge.innerText = `COMPLETED (${msg.outcome || "DONE"})`;

    student.innerText = `Finished Call: ${msg.student_name}`;
    phone.innerText = `Summary: ${msg.summary_notes || "Call saved to audit log"}`;
    
    if (msg.tentative_pay_date) {
        transcript.innerHTML = `<span class="text-emerald-400 font-semibold">Payment Commitment: Tentative Date ${msg.tentative_pay_date}</span>`;
    }

    setTimeout(() => {
        fetchCallLogs();
        fetchStats();
    }, 1000);
}

function updateTimerDisplay() {
    if (!callStartTime) return;
    const elapsed = Math.floor((Date.now() - callStartTime) / 1000);
    const m = String(Math.floor(elapsed / 60)).padStart(2, "0");
    const s = String(elapsed % 60).padStart(2, "0");
    document.getElementById("liveDurationTimer").innerText = `${m}:${s}`;
}

// ----------------- Campaign Progress -----------------
function showCampaignProgress(current, total, studentName = "") {
    const sec = document.getElementById("campaignProgressSection");
    const txt = document.getElementById("campaignProgressText");
    const bar = document.getElementById("campaignProgressBar");
    sec.classList.remove("hidden");
    
    const pct = total > 0 ? Math.round((current / total) * 100) : 0;
    txt.innerHTML = `Dialing <strong>${current} of ${total}</strong> Defaulters ${studentName ? `(${studentName})` : ''} - <strong>${pct}%</strong>`;
    bar.style.width = `${pct}%`;
}

function hideCampaignProgress() {
    const sec = document.getElementById("campaignProgressSection");
    sec.classList.add("hidden");
}

// ----------------- REST Data Calls -----------------
async function fetchStats() {
    try {
        const res = await fetch("/api/stats");
        const data = await res.json();
        renderStats(data);
    } catch (e) {
        console.error("Failed to fetch stats:", e);
    }
}

function renderStats(s) {
    document.getElementById("kpiTotalDues").innerText = `₹${Math.round(s.total_dues || 0).toLocaleString("en-IN")}`;
    document.getElementById("kpiTotalStudents").innerText = `${s.total_students || 0} Defaulters`;
    document.getElementById("kpiTotalCalls").innerText = s.total_calls || 0;
    document.getElementById("kpiContactRate").innerText = `${s.contact_rate || 0}% Contact Rate`;
    document.getElementById("kpiPromiseCount").innerText = s.promise_count || 0;
    document.getElementById("kpiPromiseAmount").innerText = `₹${Math.round(s.promise_amount || 0).toLocaleString("en-IN")} Committed`;
    document.getElementById("kpiPaidCount").innerText = s.paid_count || 0;
    document.getElementById("kpiPaidAmount").innerText = `₹${Math.round(s.paid_amount || 0).toLocaleString("en-IN")} Verified`;
    document.getElementById("kpiDisputeCount").innerText = s.dispute_count || 0;
    document.getElementById("kpiNoAnswerCount").innerText = s.no_answer_count || 0;
    document.getElementById("rosterCountBadge").innerText = s.total_students || 0;
    document.getElementById("rosterTotalDuesText").innerText = `₹${Math.round(s.total_dues || 0).toLocaleString("en-IN")}`;
}

async function fetchCallLogs() {
    try {
        const res = await fetch("/api/calls");
        allCallLogs = await res.json();
        renderCallLogs(allCallLogs);
    } catch (e) {
        console.error("Failed to fetch logs:", e);
    }
}

function renderCallLogs(logs) {
    const tbody = document.getElementById("callLogsTableBody");
    if (!logs || logs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-10 text-slate-500">No calls executed yet. Click 'Talk to AI (Mic Demo)' or 'Launch Campaign' to start.</td></tr>`;
        return;
    }

    tbody.innerHTML = logs.map(log => {
        let badgeColor = "bg-slate-800 text-slate-400 border-slate-700";
        if (log.outcome === "PROMISE_TO_PAY") badgeColor = "bg-emerald-500/10 text-emerald-400 border-emerald-500/30 font-semibold";
        if (log.outcome === "ALREADY_PAID") badgeColor = "bg-teal-500/10 text-teal-400 border-teal-500/30 font-semibold";
        if (log.outcome === "EXTENSION_REQUEST") badgeColor = "bg-amber-500/10 text-amber-400 border-amber-500/30";
        if (log.outcome === "DISPUTED") badgeColor = "bg-rose-500/10 text-rose-400 border-rose-500/30";
        if (log.outcome === "WRONG_NUMBER") badgeColor = "bg-red-500/10 text-red-400 border-red-500/30";

        const starColor = log.manual_followup ? "text-amber-400 fill-amber-400" : "text-slate-600 hover:text-slate-400";

        return `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="px-4 py-3">
                    <div class="font-semibold text-white">${log.student_name}</div>
                    <div class="text-[11px] text-slate-400">${log.parent_name || 'Guardian'}</div>
                </td>
                <td class="px-4 py-3 font-mono text-slate-300">${log.mobile_number}</td>
                <td class="px-4 py-3 font-semibold text-rose-300">₹${Math.round(log.pending_amount).toLocaleString("en-IN")}</td>
                <td class="px-4 py-3">
                    <span class="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-300 border border-slate-700">${log.call_status}</span>
                </td>
                <td class="px-4 py-3">
                    <span class="px-2.5 py-1 rounded-full text-[11px] border ${badgeColor}">${log.outcome.replace('_', ' ')}</span>
                </td>
                <td class="px-4 py-3 font-mono text-slate-200">
                    ${log.tentative_pay_date ? `<span class="text-emerald-400 font-bold">${log.tentative_pay_date}</span>` : '<span class="text-slate-500">-</span>'}
                </td>
                <td class="px-4 py-3 max-w-xs truncate text-slate-400" title="${log.summary_notes || log.raw_transcript}">
                    ${log.summary_notes || log.raw_transcript || '<span class="text-slate-600">Pending audio...</span>'}
                </td>
                <td class="px-4 py-3 text-right space-x-2">
                    <button onclick="openTranscriptModal('${log.call_uuid}')" class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition" title="View Full Transcript">
                        <i data-lucide="file-text" class="h-3.5 w-3.5"></i>
                    </button>
                    <button onclick="toggleFlag('${log.call_uuid}')" class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 ${starColor} transition" title="Toggle Manual Follow-up Flag">
                        <i data-lucide="flag" class="h-3.5 w-3.5"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join("");

    lucide.createIcons();
}

function filterLogs() {
    const search = document.getElementById("logSearchInput").value.toLowerCase();
    const outcomeFilter = document.getElementById("outcomeFilterSelect").value;

    const filtered = allCallLogs.filter(log => {
        const matchesSearch = (
            (log.student_name && log.student_name.toLowerCase().includes(search)) ||
            (log.parent_name && log.parent_name.toLowerCase().includes(search)) ||
            (log.mobile_number && log.mobile_number.includes(search)) ||
            (log.summary_notes && log.summary_notes.toLowerCase().includes(search))
        );
        const matchesOutcome = outcomeFilter === "ALL" || log.outcome === outcomeFilter;
        return matchesSearch && matchesOutcome;
    });

    renderCallLogs(filtered);
}

async function fetchRoster() {
    try {
        const res = await fetch("/api/records");
        allRoster = await res.json();
        renderRoster(allRoster);
    } catch (e) {
        console.error("Failed to fetch roster:", e);
    }
}

function renderRoster(students) {
    const tbody = document.getElementById("rosterTableBody");
    if (!students || students.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-10 text-slate-500">Roster is empty. Click 'Upload Excel / PDF' or 'Load Demo Roster'.</td></tr>`;
        return;
    }

    tbody.innerHTML = students.map(s => {
        return `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="px-4 py-3 font-semibold text-white">${s.student_name}</td>
                <td class="px-4 py-3 text-slate-300">${s.parent_name || 'Guardian'}</td>
                <td class="px-4 py-3 font-mono text-slate-300">${s.mobile_number}</td>
                <td class="px-4 py-3 font-bold text-rose-400">₹${Math.round(s.pending_amount).toLocaleString("en-IN")}</td>
                <td class="px-4 py-3 font-mono text-slate-400">${s.due_date || 'N/A'}</td>
                <td class="px-4 py-3 text-slate-400">${s.course_class || '-'}</td>
                <td class="px-4 py-3 text-slate-400 max-w-xs truncate">${s.reason || 'Tuition Dues'}</td>
                <td class="px-4 py-3 text-right">
                    <button onclick="dialSingleStudent('${s.student_name}', '${s.parent_name}', '${s.mobile_number}', ${s.pending_amount}, '${s.due_date}')" class="px-3 py-1 rounded bg-sky-600/20 hover:bg-sky-600/40 text-sky-400 border border-sky-500/30 font-medium text-xs transition">
                        Call Now
                    </button>
                </td>
            </tr>
        `;
    }).join("");

    lucide.createIcons();
}

async function dialSingleStudent(student, parent, phone, amount, due) {
    try {
        const res = await fetch("/api/call/single", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                student_name: student,
                parent_name: parent,
                mobile_number: phone,
                pending_amount: amount,
                due_date: due
            })
        });
        const data = await res.json();
        switchTab("logs");
    } catch (e) {
        alert("Failed to dial: " + e.message);
    }
}

async function submitQuickDial() {
    const phone = document.getElementById("quickPhone").value.trim();
    const student = document.getElementById("quickStudent").value.trim();
    const parent = document.getElementById("quickParent").value.trim();
    const amount = parseFloat(document.getElementById("quickAmount").value || "0");
    const due = document.getElementById("quickDueDate").value;

    if (!phone) {
        alert("Please enter a mobile number.");
        return;
    }

    closeModal("quickDialModal");
    await dialSingleStudent(student, parent, phone, amount, due);
}

async function startBatchCampaign() {
    if (confirm("Launch automated outbound voice calls to all pending fee defaulters?")) {
        try {
            const res = await fetch("/api/call/batch", { method: "POST" });
            const data = await res.json();
            if (data.status === "error") {
                alert(data.message);
            } else {
                switchTab("logs");
            }
        } catch (e) {
            alert("Error launching campaign: " + e.message);
        }
    }
}

async function stopCampaign() {
    try {
        await fetch("/api/call/stop", { method: "POST" });
    } catch (e) {
        console.error("Stop failed:", e);
    }
}

async function loadSampleData() {
    try {
        await fetch("/api/sample-data", { method: "POST" });
        await fetchRoster();
        await fetchStats();
    } catch (e) {
        alert("Error loading demo data: " + e.message);
    }
}

async function clearRoster() {
    if (confirm("Clear all students from the roster?")) {
        await fetch("/api/clear-students", { method: "POST" });
        await fetchRoster();
        await fetchStats();
    }
}

async function toggleFlag(callUuid) {
    const form = new FormData();
    form.append("call_uuid", callUuid);
    await fetch("/api/call/toggle-flag", { method: "POST", body: form });
    fetchCallLogs();
}

function openModal(id) {
    document.getElementById(id).classList.remove("hidden");
    lucide.createIcons();
}

function closeModal(id) {
    document.getElementById(id).classList.add("hidden");
}

function switchTab(tab) {
    const logsBtn = document.getElementById("tabLogsBtn");
    const rosterBtn = document.getElementById("tabRosterBtn");
    const logsContent = document.getElementById("tabLogsContent");
    const rosterContent = document.getElementById("tabRosterContent");

    if (tab === "logs") {
        logsBtn.className = "px-4 py-2 rounded-xl text-xs font-semibold bg-sky-600 text-white shadow-sm transition";
        rosterBtn.className = "px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800 transition";
        logsContent.classList.remove("hidden");
        rosterContent.classList.add("hidden");
    } else {
        rosterBtn.className = "px-4 py-2 rounded-xl text-xs font-semibold bg-sky-600 text-white shadow-sm transition";
        logsBtn.className = "px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800 transition";
        rosterContent.classList.remove("hidden");
        logsContent.classList.add("hidden");
    }
}

function openTranscriptModal(callUuid) {
    const log = allCallLogs.find(l => l.call_uuid === callUuid);
    if (!log) return;

    document.getElementById("modalStudentTitle").innerText = `Transcript: ${log.student_name} (${log.mobile_number})`;
    document.getElementById("modalCallSub").innerText = `Call ID: ${log.call_uuid} • Duration: ${log.duration || 0}s`;
    document.getElementById("modalBotPrompt").innerText = `"${log.bot_response || 'Notification played for pending fees of ₹' + log.pending_amount}"`;
    document.getElementById("modalParentSpeech").innerText = log.raw_transcript ? `"${log.raw_transcript}"` : "No voice speech captured.";
    document.getElementById("modalOutcomeText").innerText = log.outcome || "PENDING";
    document.getElementById("modalTentativeDate").innerText = log.tentative_pay_date || "None";
    document.getElementById("modalNotesText").innerText = log.summary_notes || "No notes logged.";

    openModal("transcriptModal");
}

// ----------------- File Upload Handler -----------------
let selectedUploadFile = null;
function handleFileSelected(event) {
    const file = event.target.files[0];
    if (file) {
        selectedUploadFile = file;
        document.getElementById("selectedFileName").innerText = `${file.name} (${Math.round(file.size / 1024)} KB)`;
    }
}

async function submitUploadFile() {
    if (!selectedUploadFile) {
        alert("Please select an Excel, CSV, or PDF file.");
        return;
    }

    const btn = document.getElementById("uploadSubmitBtn");
    const statusMsg = document.getElementById("uploadStatusMessage");
    btn.disabled = true;
    btn.innerText = "Parsing & Ingesting...";

    const formData = new FormData();
    formData.append("file", selectedUploadFile);

    try {
        const res = await fetch("/api/upload", { method: "POST", body: formData });
        const data = await res.json();
        if (data.status === "success") {
            statusMsg.className = "text-xs rounded-lg p-2.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
            statusMsg.innerText = data.message;
            statusMsg.classList.remove("hidden");
            setTimeout(() => {
                closeModal("uploadModal");
                switchTab("roster");
                fetchRoster();
                fetchStats();
            }, 1200);
        } else {
            statusMsg.className = "text-xs rounded-lg p-2.5 bg-rose-500/10 text-rose-400 border border-rose-500/20";
            statusMsg.innerText = data.message;
            statusMsg.classList.remove("hidden");
        }
    } catch (e) {
        statusMsg.className = "text-xs rounded-lg p-2.5 bg-rose-500/10 text-rose-400 border border-rose-500/20";
        statusMsg.innerText = "Upload failed: " + e.message;
        statusMsg.classList.remove("hidden");
    } finally {
        btn.disabled = false;
        btn.innerText = "Upload & Ingest";
    }
}

// ----------------- Settings & Provider Toggle -----------------
function toggleProviderFields() {
    const prov = document.getElementById("settingProvider").value;
    const twilioSec = document.getElementById("twilioSection");
    const plivoSec = document.getElementById("plivoSection");

    if (prov === "twilio") {
        twilioSec.classList.remove("hidden");
        plivoSec.classList.add("hidden");
    } else if (prov === "plivo") {
        plivoSec.classList.remove("hidden");
        twilioSec.classList.add("hidden");
    } else {
        twilioSec.classList.add("hidden");
        plivoSec.classList.add("hidden");
    }

    // Update header badge
    const badge = document.getElementById("telephonyModeText");
    if (prov === "browser") badge.innerText = "In-Browser Mic Demo";
    else if (prov === "twilio") badge.innerText = "Twilio Voice (Live)";
    else if (prov === "plivo") badge.innerText = "Plivo Voice (Live)";
    else badge.innerText = "Simulation Active";
}

async function loadSettings() {
    try {
        const res = await fetch("/api/settings");
        const s = await res.json();
        
        const prov = s.TELEPHONY_PROVIDER || "browser";
        document.getElementById("settingProvider").value = prov;
        
        document.getElementById("settingTwilioSid").value = s.TWILIO_ACCOUNT_SID || "";
        document.getElementById("settingTwilioPhone").value = s.TWILIO_PHONE_NUMBER || "";
        
        document.getElementById("settingPlivoAuthId").value = s.PLIVO_AUTH_ID || "";
        document.getElementById("settingPlivoPhone").value = s.PLIVO_PHONE_NUMBER || "";
        document.getElementById("settingWebhookUrl").value = s.PUBLIC_WEBHOOK_URL || "";
        
        toggleProviderFields();
    } catch (e) {
        console.error("Failed to load settings:", e);
    }
}

async function saveSettings() {
    const prov = document.getElementById("settingProvider").value;
    
    const twilioSid = document.getElementById("settingTwilioSid").value.trim();
    const twilioToken = document.getElementById("settingTwilioToken").value.trim();
    const twilioPhone = document.getElementById("settingTwilioPhone").value.trim();

    const plivoAuthId = document.getElementById("settingPlivoAuthId").value.trim();
    const plivoToken = document.getElementById("settingPlivoAuthToken").value.trim();
    const plivoPhone = document.getElementById("settingPlivoPhone").value.trim();

    const webhook = document.getElementById("settingWebhookUrl").value.trim();
    const openaiKey = document.getElementById("settingOpenAIKey").value.trim();

    const payload = {
        TELEPHONY_PROVIDER: prov,
        TWILIO_ACCOUNT_SID: twilioSid,
        TWILIO_PHONE_NUMBER: twilioPhone,
        PLIVO_AUTH_ID: plivoAuthId,
        PLIVO_PHONE_NUMBER: plivoPhone,
        PUBLIC_WEBHOOK_URL: webhook
    };
    if (twilioToken) payload.TWILIO_AUTH_TOKEN = twilioToken;
    if (plivoToken) payload.PLIVO_AUTH_TOKEN = plivoToken;
    if (openaiKey) payload.OPENAI_API_KEY = openaiKey;

    try {
        await fetch("/api/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        alert("Configuration saved successfully!");
        closeModal("settingsModal");
        loadSettings();
    } catch (e) {
        alert("Failed to save settings: " + e.message);
    }
}

function downloadExport(type) {
    if (type === "excel") {
        window.location.href = "/api/export/excel";
    } else {
        window.location.href = "/api/export/pdf";
    }
}
