import os
import asyncio
import random
from typing import Dict, Any, Optional
import plivo
from app.database import get_setting, update_call_log, create_call_log
from app.llm_extractor import analyze_caller_speech

# Simulation scenarios for realistic live testing
SIMULATED_SCENARIOS = [
    {
        "speech": "I already paid fifteen thousand rupees yesterday evening using Google Pay UPI.",
        "duration": 28
    },
    {
        "speech": "My salary will be credited on 5th, so I will definitely clear the pending fee by next Monday.",
        "duration": 34
    },
    {
        "speech": "I will pay on 12th of November, please send me the payment link on WhatsApp.",
        "duration": 31
    },
    {
        "speech": "There is a mistake in the fee amount, my daughter received a 25% merit scholarship.",
        "duration": 42
    },
    {
        "speech": "Can I pay in two installments? I can give half next week and rest next month.",
        "duration": 36
    },
    {
        "speech": "Wrong number. There is no student by this name at this phone number.",
        "duration": 18
    }
]

def get_plivo_client() -> Optional[plivo.rest.Client]:
    auth_id = get_setting("PLIVO_AUTH_ID")
    auth_token = get_setting("PLIVO_AUTH_TOKEN")
    if auth_id and auth_token and len(auth_id.strip()) > 5 and len(auth_token.strip()) > 5:
        try:
            return plivo.rest.Client(auth_id.strip(), auth_token.strip())
        except Exception as e:
            print(f"Error creating Plivo client: {e}")
    return None

def generate_answer_xml(student_name: str, parent_name: str, amount: float, due_date: str, institute: str, action_url: str) -> str:
    """Generates Plivo XML (<Response><GetInput><Speak>...</Speak></GetInput></Response>)"""
    greeting = f"Hello {parent_name if parent_name and parent_name != 'Guardian' else ''}".strip()
    speech_prompt = (
        f"{greeting}. This is an automated notification from {institute}. "
        f"We are calling regarding pending fees of rupees {int(amount)} for student {student_name}, "
        f"which was due on {due_date}. "
        f"Please let us know: have you already paid, or could you provide a tentative date by which you will pay?"
    )
    
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <GetInput action="{action_url}" method="POST" inputType="speech" speechEndTimeout="2" executionTimeout="14" language="en-IN">
        <Speak voice="Polly.Aditi">{speech_prompt}</Speak>
    </GetInput>
    <Speak voice="Polly.Aditi">We did not receive your response. We will follow up later. Thank you.</Speak>
    <Hangup/>
</Response>"""
    return xml

def generate_response_xml(bot_reply: str) -> str:
    """Generates closing acknowledgment XML."""
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak voice="Polly.Aditi">{bot_reply}</Speak>
    <Hangup/>
</Response>"""
    return xml

async def trigger_call(
    student_data: Dict[str, Any], 
    ws_broadcast_func,
    webhook_base: str = ""
) -> Dict[str, Any]:
    """
    Initiates an outbound call via Plivo REST API.
    If credentials are missing or SIMULATION_MODE is true, runs real-time simulation.
    """
    call_uuid = f"call-{int(asyncio.get_event_loop().time() * 1000)}-{random.randint(100, 999)}"
    phone = student_data.get("mobile_number", "")
    student_name = student_data.get("student_name", "Student")
    parent_name = student_data.get("parent_name", "Parent")
    amount = float(student_data.get("pending_amount", 0.0))
    due_date = student_data.get("due_date", "2026-10-30")
    institute = student_data.get("institute_name", "Apex Learning Academy")
    
    # 1. Record in DB
    create_call_log({
        "call_uuid": call_uuid,
        "student_id": student_data.get("student_id", ""),
        "student_name": student_name,
        "parent_name": parent_name,
        "mobile_number": phone,
        "pending_amount": amount,
        "call_status": "DIALING",
        "outcome": "PENDING"
    })
    
    # Check if Plivo client is configured and active
    client = get_plivo_client()
    sim_mode = get_setting("SIMULATION_MODE", "true").lower() == "true"
    plivo_from = get_setting("PLIVO_PHONE_NUMBER")
    
    if client and not sim_mode and plivo_from and webhook_base:
        try:
            answer_url = f"{webhook_base}/plivo/answer?call_uuid={call_uuid}&student={student_name}&parent={parent_name}&amount={amount}&due={due_date}&inst={institute}"
            hangup_url = f"{webhook_base}/plivo/status?call_uuid={call_uuid}"
            
            response = client.calls.create(
                from_=plivo_from,
                to_=phone,
                answer_url=answer_url,
                answer_method="POST",
                hangup_url=hangup_url,
                hangup_method="POST"
            )
            
            real_uuid = response.get("request_uuid", call_uuid)
            update_call_log(call_uuid, {"call_status": "RINGING"})
            
            await ws_broadcast_func({
                "type": "CALL_STATUS",
                "call_uuid": call_uuid,
                "student_name": student_name,
                "phone": phone,
                "status": "RINGING",
                "message": f"Calling {phone} via Plivo..."
            })
            return {"status": "success", "mode": "PLIVO_LIVE", "call_uuid": real_uuid}
        except Exception as e:
            print(f"Plivo live dial failed: {e}. Falling back to simulation.")
    
    # Fallback to Asynchronous Real-Time Simulation
    asyncio.create_task(run_simulated_call_lifecycle(call_uuid, student_data, ws_broadcast_func))
    return {"status": "success", "mode": "SIMULATION", "call_uuid": call_uuid}

async def run_simulated_call_lifecycle(call_uuid: str, student_data: Dict[str, Any], ws_broadcast):
    """
    Simulates real-time call states with realistic delays and pushes events to WebSocket.
    """
    student_name = student_data.get("student_name", "Student")
    phone = student_data.get("mobile_number", "")
    amount = float(student_data.get("pending_amount", 0.0))
    
    # Step 1: DIALING
    await ws_broadcast({
        "type": "CALL_EVENT",
        "call_uuid": call_uuid,
        "student_name": student_name,
        "phone": phone,
        "status": "DIALING",
        "step": "Initiating outbound SIP connection...",
        "transcript": ""
    })
    await asyncio.sleep(2.0)
    
    # Step 2: RINGING
    update_call_log(call_uuid, {"call_status": "RINGING"})
    await ws_broadcast({
        "type": "CALL_EVENT",
        "call_uuid": call_uuid,
        "student_name": student_name,
        "phone": phone,
        "status": "RINGING",
        "step": "Phone is ringing...",
        "transcript": ""
    })
    await asyncio.sleep(3.0)
    
    # Step 3: ANSWERED & IN PROGRESS
    update_call_log(call_uuid, {"call_status": "IN_PROGRESS"})
    await ws_broadcast({
        "type": "CALL_EVENT",
        "call_uuid": call_uuid,
        "student_name": student_name,
        "phone": phone,
        "status": "IN_PROGRESS",
        "step": f"Call answered! Bot is speaking fee notice (₹{int(amount)})...",
        "transcript": "Bot: 'Hello, calling regarding pending fee dues...'"
    })
    await asyncio.sleep(4.0)
    
    # Step 4: CALLER IS SPEAKING (Speech Captured)
    scenario = random.choice(SIMULATED_SCENARIOS)
    spoken_text = scenario["speech"]
    duration = scenario["duration"]
    
    await ws_broadcast({
        "type": "CALL_EVENT",
        "call_uuid": call_uuid,
        "student_name": student_name,
        "phone": phone,
        "status": "SPEECH_RECOGNITION",
        "step": "Parent is speaking... processing speech audio...",
        "transcript": f"Parent: \"{spoken_text}\""
    })
    await asyncio.sleep(2.5)
    
    # Step 5: EXTRACTING INTENT & REASONING
    openai_key = get_setting("OPENAI_API_KEY", "")
    extraction = analyze_caller_speech(spoken_text, student_name, amount, openai_key)
    
    # Step 6: COMPLETED
    update_call_log(call_uuid, {
        "call_status": "COMPLETED",
        "outcome": extraction["outcome"],
        "tentative_pay_date": extraction["tentative_pay_date"] or "",
        "raw_transcript": spoken_text,
        "bot_response": extraction["bot_reply"],
        "summary_notes": extraction["summary_notes"],
        "manual_followup": extraction["manual_followup"],
        "duration": duration
    })
    
    await ws_broadcast({
        "type": "CALL_COMPLETED",
        "call_uuid": call_uuid,
        "student_name": student_name,
        "phone": phone,
        "status": "COMPLETED",
        "outcome": extraction["outcome"],
        "tentative_pay_date": extraction["tentative_pay_date"],
        "summary_notes": extraction["summary_notes"],
        "bot_response": extraction["bot_reply"],
        "duration": duration,
        "step": f"Call finished ({duration}s). Outcome: {extraction['outcome']}"
    })
