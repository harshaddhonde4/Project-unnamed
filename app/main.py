import os
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Response, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.database import (
    init_db, get_dashboard_stats, get_students, insert_students, clear_students,
    get_call_logs, get_all_settings, set_setting, get_setting,
    update_call_log, toggle_manual_followup
)
from app.parsers import parse_uploaded_file, get_sample_records
from app.telephony_service import (
    trigger_outbound_call,
    generate_twilio_answer_twiml, generate_twilio_response_twiml,
    generate_plivo_answer_xml, generate_plivo_response_xml
)
from app.llm_extractor import analyze_caller_speech
from app.export_service import generate_excel_export, generate_pdf_summary

app = FastAPI(title="Voice AI Fee Collection System", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

# WebSocket Manager for Live Screen Updates
class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

ws_manager = WebSocketManager()

campaign_state = {
    "is_running": False,
    "should_stop": False,
    "current_index": 0,
    "total": 0
}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        stats = get_dashboard_stats()
        await websocket.send_json({"type": "STATS_UPDATE", "data": stats})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>System Initializing...</h1>")

# ----------------- Core REST API Endpoints -----------------

@app.get("/api/stats")
async def api_get_stats():
    return get_dashboard_stats()

@app.get("/api/records")
async def api_get_records():
    return get_students()

@app.get("/api/calls")
async def api_get_calls():
    return get_call_logs(limit=150)

@app.post("/api/upload")
async def api_upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    try:
        records = parse_uploaded_file(contents, file.filename)
        if not records:
            return {"status": "error", "message": "No valid student fee records found in file."}
        insert_students(records)
        stats = get_dashboard_stats()
        await ws_manager.broadcast({"type": "STATS_UPDATE", "data": stats})
        return {
            "status": "success",
            "message": f"Successfully parsed and ingested {len(records)} student fee records.",
            "count": len(records)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/sample-data")
async def api_load_sample_data():
    samples = get_sample_records()
    insert_students(samples)
    stats = get_dashboard_stats()
    await ws_manager.broadcast({"type": "STATS_UPDATE", "data": stats})
    return {"status": "success", "count": len(samples), "records": samples}

@app.post("/api/clear-students")
async def api_clear_students():
    clear_students()
    stats = get_dashboard_stats()
    await ws_manager.broadcast({"type": "STATS_UPDATE", "data": stats})
    return {"status": "success", "message": "All student records cleared."}

class SingleCallRequest(BaseModel):
    student_name: str
    parent_name: Optional[str] = "Guardian"
    mobile_number: str
    pending_amount: float
    due_date: Optional[str] = "2026-10-30"
    institute_name: Optional[str] = "Apex Learning Academy"

@app.post("/api/call/single")
async def api_call_single(req: SingleCallRequest):
    webhook_base = get_setting("PUBLIC_WEBHOOK_URL", "")
    res = await trigger_outbound_call(req.dict(), ws_manager.broadcast, webhook_base=webhook_base)
    stats = get_dashboard_stats()
    await ws_manager.broadcast({"type": "STATS_UPDATE", "data": stats})
    return res

# In-Browser Softphone Speech Callback (Takes user's real mic input!)
class BrowserResponseRequest(BaseModel):
    call_uuid: str
    student_name: str
    pending_amount: float
    speech_text: str
    duration: Optional[int] = 20

@app.post("/api/call/browser-response")
async def api_browser_call_response(req: BrowserResponseRequest):
    openai_key = get_setting("OPENAI_API_KEY", "")
    extraction = analyze_caller_speech(req.speech_text, req.student_name, req.pending_amount, openai_key)
    
    update_call_log(req.call_uuid, {
        "call_status": "COMPLETED",
        "outcome": extraction["outcome"],
        "tentative_pay_date": extraction["tentative_pay_date"] or "",
        "raw_transcript": req.speech_text,
        "bot_response": extraction["bot_reply"],
        "summary_notes": extraction["summary_notes"],
        "manual_followup": extraction["manual_followup"],
        "duration": req.duration
    })
    
    stats = get_dashboard_stats()
    await ws_manager.broadcast({
        "type": "CALL_COMPLETED",
        "call_uuid": req.call_uuid,
        "student_name": req.student_name,
        "status": "COMPLETED",
        "outcome": extraction["outcome"],
        "tentative_pay_date": extraction["tentative_pay_date"],
        "summary_notes": extraction["summary_notes"],
        "bot_response": extraction["bot_reply"],
        "duration": req.duration,
        "step": f"Call finished ({req.duration}s). Outcome: {extraction['outcome']}"
    })
    await ws_manager.broadcast({"type": "STATS_UPDATE", "data": stats})
    
    return {
        "status": "success",
        "bot_reply": extraction["bot_reply"],
        "outcome": extraction["outcome"],
        "tentative_pay_date": extraction["tentative_pay_date"]
    }

async def run_batch_campaign():
    global campaign_state
    students = get_students()
    campaign_state["is_running"] = True
    campaign_state["should_stop"] = False
    campaign_state["total"] = len(students)
    campaign_state["current_index"] = 0
    
    webhook_base = get_setting("PUBLIC_WEBHOOK_URL", "")
    throttle_sec = int(get_setting("CALLING_THROTTLE_SECONDS", "5"))
    
    await ws_manager.broadcast({
        "type": "CAMPAIGN_STARTED", 
        "total": len(students)
    })
    
    for idx, student in enumerate(students):
        if campaign_state["should_stop"]:
            break
            
        campaign_state["current_index"] = idx + 1
        await ws_manager.broadcast({
            "type": "CAMPAIGN_PROGRESS",
            "current": idx + 1,
            "total": len(students),
            "student_name": student.get("student_name")
        })
        
        await trigger_outbound_call(student, ws_manager.broadcast, webhook_base=webhook_base)
        await asyncio.sleep(throttle_sec)
        
    campaign_state["is_running"] = False
    stats = get_dashboard_stats()
    await ws_manager.broadcast({
        "type": "CAMPAIGN_FINISHED",
        "total": len(students),
        "stats": stats
    })

@app.post("/api/call/batch")
async def api_call_batch():
    if campaign_state["is_running"]:
        return {"status": "error", "message": "A campaign is already running."}
    students = get_students()
    if not students:
        return {"status": "error", "message": "No students in roster. Please upload a file first."}
        
    asyncio.create_task(run_batch_campaign())
    return {"status": "success", "message": f"Campaign started for {len(students)} contacts."}

@app.post("/api/call/stop")
async def api_call_stop():
    global campaign_state
    campaign_state["should_stop"] = True
    campaign_state["is_running"] = False
    await ws_manager.broadcast({"type": "CAMPAIGN_STOPPED"})
    return {"status": "success", "message": "Campaign stopping..."}

@app.post("/api/call/toggle-flag")
async def api_toggle_flag(call_uuid: str = Form(...)):
    new_val = toggle_manual_followup(call_uuid)
    stats = get_dashboard_stats()
    await ws_manager.broadcast({"type": "STATS_UPDATE", "data": stats})
    return {"status": "success", "manual_followup": new_val}

@app.get("/api/settings")
async def api_get_settings():
    all_s = get_all_settings()
    token = all_s.get("PLIVO_AUTH_TOKEN", "")
    t_token = all_s.get("TWILIO_AUTH_TOKEN", "")
    all_s["PLIVO_AUTH_TOKEN_MASKED"] = (token[:4] + "********") if len(token) > 5 else ""
    all_s["TWILIO_AUTH_TOKEN_MASKED"] = (t_token[:4] + "********") if len(t_token) > 5 else ""
    return all_s

class SettingsUpdate(BaseModel):
    TELEPHONY_PROVIDER: Optional[str] = None
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    PLIVO_AUTH_ID: Optional[str] = None
    PLIVO_AUTH_TOKEN: Optional[str] = None
    PLIVO_PHONE_NUMBER: Optional[str] = None
    PUBLIC_WEBHOOK_URL: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

@app.post("/api/settings")
async def api_update_settings(settings: SettingsUpdate):
    for k, v in settings.dict(exclude_unset=True).items():
        if v is not None:
            if (k in ["PLIVO_AUTH_TOKEN", "TWILIO_AUTH_TOKEN"]) and v.strip() == "":
                continue
            set_setting(k, v.strip())
    return {"status": "success", "message": "Settings updated successfully."}

# ----------------- File Export Endpoints -----------------

@app.get("/api/export/excel")
async def api_export_excel():
    calls = get_call_logs(limit=1000)
    data = generate_excel_export(calls)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Call_Disposition_Audit_Report.xlsx"}
    )

@app.get("/api/export/pdf")
async def api_export_pdf():
    calls = get_call_logs(limit=100)
    stats = get_dashboard_stats()
    pdf_bytes = generate_pdf_summary(calls, stats)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=Executive_Fee_Call_Report.pdf"}
    )

# ----------------- Twilio Live Webhooks (Gmail Supported) -----------------

@app.api_route("/twilio/answer", methods=["GET", "POST"])
async def twilio_answer_webhook(
    request: Request,
    call_uuid: str = "",
    student: str = "Student",
    parent: str = "Parent",
    amount: float = 0.0,
    due: str = "2026-10-30",
    inst: str = "Apex Learning Academy"
):
    update_call_log(call_uuid, {"call_status": "IN_PROGRESS"})
    await ws_manager.broadcast({
        "type": "CALL_EVENT",
        "call_uuid": call_uuid,
        "status": "IN_PROGRESS",
        "student_name": student,
        "step": f"Call answered by {parent}. Bot speaking notice...",
        "transcript": f"Bot: 'Notification for fee of Rs. {amount} due on {due}'"
    })
    webhook_base = get_setting("PUBLIC_WEBHOOK_URL", "")
    action_url = f"{webhook_base}/twilio/speech?call_uuid={call_uuid}&student={student}&amount={amount}"
    twiml = generate_twilio_answer_twiml(student, parent, amount, due, inst, action_url)
    return Response(content=twiml, media_type="application/xml")

@app.api_route("/twilio/speech", methods=["GET", "POST"])
async def twilio_speech_webhook(
    request: Request,
    call_uuid: str = "",
    student: str = "Student",
    amount: float = 0.0
):
    if request.method == "POST":
        form_data = await request.form()
        speech_text = form_data.get("SpeechResult", "")
    else:
        speech_text = request.query_params.get("SpeechResult", "")
    
    await ws_manager.broadcast({
        "type": "CALL_EVENT",
        "call_uuid": call_uuid,
        "status": "SPEECH_RECOGNITION",
        "student_name": student,
        "step": "Received speech from caller...",
        "transcript": f"Caller: \"{speech_text}\""
    })
    
    openai_key = get_setting("OPENAI_API_KEY", "")
    extraction = analyze_caller_speech(speech_text, student, amount, openai_key)
    
    update_call_log(call_uuid, {
        "call_status": "COMPLETED",
        "outcome": extraction["outcome"],
        "tentative_pay_date": extraction["tentative_pay_date"] or "",
        "raw_transcript": speech_text,
        "bot_response": extraction["bot_reply"],
        "summary_notes": extraction["summary_notes"],
        "manual_followup": extraction["manual_followup"]
    })
    
    stats = get_dashboard_stats()
    await ws_manager.broadcast({
        "type": "CALL_COMPLETED",
        "call_uuid": call_uuid,
        "student_name": student,
        "status": "COMPLETED",
        "outcome": extraction["outcome"],
        "tentative_pay_date": extraction["tentative_pay_date"],
        "summary_notes": extraction["summary_notes"],
        "bot_response": extraction["bot_reply"],
        "step": f"Finished. Outcome: {extraction['outcome']}"
    })
    await ws_manager.broadcast({"type": "STATS_UPDATE", "data": stats})
    
    webhook_base = get_setting("PUBLIC_WEBHOOK_URL", "")
    action_url = f"{webhook_base}/twilio/speech?call_uuid={call_uuid}&student={student}&amount={amount}"
    turn = request.query_params.get("turn", "1")

    # If response is UNCLEAR and this is turn 1 or 2, re-prompt caller for a proper response!
    if extraction["outcome"] == "UNCLEAR" and turn != "final":
        from app.telephony_service import generate_twilio_reprompt_twiml
        reprompt_twiml = generate_twilio_reprompt_twiml(amount, action_url)
        return Response(content=reprompt_twiml, media_type="application/xml")
        
    twiml = generate_twilio_response_twiml(extraction["bot_reply"])
    return Response(content=twiml, media_type="application/xml")

@app.api_route("/twilio/status", methods=["GET", "POST"])
async def twilio_status_webhook(request: Request, call_uuid: str = ""):
    if request.method == "POST":
        form_data = await request.form()
        status = form_data.get("CallStatus", "COMPLETED").upper()
        duration = int(form_data.get("CallDuration", 0))
    else:
        status = request.query_params.get("CallStatus", "COMPLETED").upper()
        duration = int(request.query_params.get("CallDuration", 0))
        
    update_call_log(call_uuid, {"call_status": status, "duration": duration})
    stats = get_dashboard_stats()
    await ws_manager.broadcast({"type": "STATS_UPDATE", "data": stats})
    return Response(content="<Response></Response>", media_type="application/xml")

# ----------------- Plivo Live Webhooks -----------------

@app.post("/plivo/answer")
async def plivo_answer_webhook(
    call_uuid: str = "",
    student: str = "Student",
    parent: str = "Parent",
    amount: float = 0.0,
    due: str = "2026-10-30",
    inst: str = "Apex Learning Academy"
):
    update_call_log(call_uuid, {"call_status": "IN_PROGRESS"})
    webhook_base = get_setting("PUBLIC_WEBHOOK_URL", "")
    action_url = f"{webhook_base}/plivo/speech?call_uuid={call_uuid}&student={student}&amount={amount}"
    xml_content = generate_plivo_answer_xml(student, parent, amount, due, inst, action_url)
    return Response(content=xml_content, media_type="application/xml")

@app.post("/plivo/speech")
async def plivo_speech_webhook(
    request: Request,
    call_uuid: str = "",
    student: str = "Student",
    amount: float = 0.0
):
    form_data = await request.form()
    speech_text = form_data.get("Speech", "")
    openai_key = get_setting("OPENAI_API_KEY", "")
    extraction = analyze_caller_speech(speech_text, student, amount, openai_key)
    
    update_call_log(call_uuid, {
        "call_status": "COMPLETED",
        "outcome": extraction["outcome"],
        "tentative_pay_date": extraction["tentative_pay_date"] or "",
        "raw_transcript": speech_text,
        "bot_response": extraction["bot_reply"],
        "summary_notes": extraction["summary_notes"],
        "manual_followup": extraction["manual_followup"]
    })
    
    stats = get_dashboard_stats()
    await ws_manager.broadcast({
        "type": "CALL_COMPLETED",
        "call_uuid": call_uuid,
        "student_name": student,
        "status": "COMPLETED",
        "outcome": extraction["outcome"],
        "tentative_pay_date": extraction["tentative_pay_date"],
        "summary_notes": extraction["summary_notes"],
        "bot_response": extraction["bot_reply"],
        "step": f"Finished. Outcome: {extraction['outcome']}"
    })
    await ws_manager.broadcast({"type": "STATS_UPDATE", "data": stats})
    
    xml_reply = generate_plivo_response_xml(extraction["bot_reply"])
    return Response(content=xml_reply, media_type="application/xml")

@app.post("/plivo/status")
async def plivo_status_webhook(request: Request, call_uuid: str = ""):
    form_data = await request.form()
    status = form_data.get("CallStatus", "COMPLETED").upper()
    duration = int(form_data.get("Duration", 0))
    update_call_log(call_uuid, {"call_status": status, "duration": duration})
    stats = get_dashboard_stats()
    await ws_manager.broadcast({"type": "STATS_UPDATE", "data": stats})
    return Response(content="<Response></Response>", media_type="application/xml")
