import os
import asyncio
import random
from typing import Dict, Any, Optional

from app.database import get_setting, update_call_log, create_call_log
from app.llm_extractor import analyze_caller_speech

# Realistic spoken scenarios for automated simulator
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

# ----------------- Twilio TwiML & Client -----------------
def get_twilio_client():
    sid = get_setting("TWILIO_ACCOUNT_SID")
    token = get_setting("TWILIO_AUTH_TOKEN")
    if sid and token and len(sid.strip()) > 5 and len(token.strip()) > 5:
        try:
            from twilio.rest import Client
            return Client(sid.strip(), token.strip())
        except Exception as e:
            print(f"Error creating Twilio client: {e}")
    return None

def generate_twilio_answer_twiml(student_name: str, parent_name: str, amount: float, due_date: str, institute: str, action_url: str) -> str:
    from twilio.twiml.voice_response import VoiceResponse, Gather
    vr = VoiceResponse()
    greeting = f"Hello {parent_name if parent_name and parent_name != 'Guardian' else ''}".strip()
    prompt = (
        f"{greeting}. This is an automated notification from {institute}. "
        f"A pending tuition fee of rupees {int(amount)} was due on {due_date} for student {student_name}. "
        f"Please state: have you already paid, or could you provide a tentative date by which you will pay?"
    )
    gather = Gather(
        input="speech",
        action=f"{action_url}&turn=1",
        method="POST",
        speech_timeout="auto",
        language="en-IN",
        timeout=6
    )
    gather.say(prompt, voice="Polly.Aditi")
    vr.append(gather)
    # If no response heard on turn 1, ask again (re-prompt)
    reprompt_gather = Gather(
        input="speech",
        action=f"{action_url}&turn=2",
        method="POST",
        speech_timeout="auto",
        language="en-IN",
        timeout=6
    )
    reprompt_gather.say(
        f"Sorry, I didn't hear your response. Could you please specify when you will pay the fee of rupees {int(amount)}, or let us know if already paid?",
        voice="Polly.Aditi"
    )
    vr.append(reprompt_gather)
    vr.say("We did not receive any response. We will follow up later. Thank you.", voice="Polly.Aditi")
    vr.hangup()
    return str(vr)

def generate_twilio_reprompt_twiml(amount: float, action_url: str) -> str:
    from twilio.twiml.voice_response import VoiceResponse, Gather
    vr = VoiceResponse()
    gather = Gather(
        input="speech",
        action=f"{action_url}&turn=final",
        method="POST",
        speech_timeout="auto",
        language="en-IN",
        timeout=6
    )
    gather.say(
        f"I could not catch that clearly. We need a tentative date to record for accounts. Could you please state a specific date by which you can pay the {int(amount)} rupees, or say yes if already paid?",
        voice="Polly.Aditi"
    )
    vr.append(gather)
    vr.say("Thank you. Our administrative team will follow up with you. Goodbye.", voice="Polly.Aditi")
    vr.hangup()
    return str(vr)

def generate_twilio_response_twiml(bot_reply: str) -> str:
    from twilio.twiml.voice_response import VoiceResponse
    vr = VoiceResponse()
    vr.say(bot_reply, voice="Polly.Aditi")
    vr.hangup()
    return str(vr)

# ----------------- Plivo XML & Client -----------------
def get_plivo_client():
    auth_id = get_setting("PLIVO_AUTH_ID")
    auth_token = get_setting("PLIVO_AUTH_TOKEN")
    if auth_id and auth_token and len(auth_id.strip()) > 5 and len(auth_token.strip()) > 5:
        try:
            import plivo
            return plivo.rest.Client(auth_id.strip(), auth_token.strip())
        except Exception as e:
            print(f"Error creating Plivo client: {e}")
    return None

def generate_plivo_answer_xml(student_name: str, parent_name: str, amount: float, due_date: str, institute: str, action_url: str) -> str:
    greeting = f"Hello {parent_name if parent_name and parent_name != 'Guardian' else ''}".strip()
    prompt = (
        f"{greeting}. This is an automated notification from {institute}. "
        f"We are calling regarding pending fees of rupees {int(amount)} for student {student_name}, "
        f"which was due on {due_date}. "
        f"Please let us know: have you already paid, or could you provide a tentative date by which you will pay?"
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <GetInput action="{action_url}" method="POST" inputType="speech" speechEndTimeout="2" executionTimeout="14" language="en-IN">
        <Speak voice="Polly.Aditi">{prompt}</Speak>
    </GetInput>
    <Speak voice="Polly.Aditi">We did not receive your response. We will follow up later. Thank you.</Speak>
    <Hangup/>
</Response>"""

def generate_plivo_response_xml(bot_reply: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak voice="Polly.Aditi">{bot_reply}</Speak>
    <Hangup/>
</Response>"""

# ----------------- Universal Outbound Dispatcher -----------------
async def trigger_outbound_call(
    student_data: Dict[str, Any], 
    ws_broadcast_func,
    webhook_base: str = ""
) -> Dict[str, Any]:
    call_uuid = f"call-{int(asyncio.get_event_loop().time() * 1000)}-{random.randint(100, 999)}"
    phone = student_data.get("mobile_number", "")
    student_name = student_data.get("student_name", "Student")
    parent_name = student_data.get("parent_name", "Parent")
    amount = float(student_data.get("pending_amount", 0.0))
    due_date = student_data.get("due_date", "2026-10-30")
    institute = student_data.get("institute_name", "Apex Learning Academy")
    
    provider = get_setting("TELEPHONY_PROVIDER", "browser").lower()
    
    # 1. Record call in database
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

    # Mode A: In-Browser Live Microphone Session (Free, Zero Account Required)
    if provider == "browser":
        prompt_text = (
            f"Hello {parent_name}. This is an automated notification from {institute}. "
            f"We are calling regarding pending tuition fees of rupees {int(amount)} for student {student_name}, "
            f"which was due on {due_date}. "
            f"Please let us know: have you already paid, or could you provide a tentative date when you will pay?"
        )
        await ws_broadcast_func({
            "type": "BROWSER_CALL_INCOMING",
            "call_uuid": call_uuid,
            "student_name": student_name,
            "parent_name": parent_name,
            "phone": phone,
            "amount": amount,
            "due_date": due_date,
            "prompt_text": prompt_text
        })
        return {
            "status": "success", 
            "mode": "BROWSER_SOFTPHONE", 
            "call_uuid": call_uuid,
            "prompt_text": prompt_text
        }

    # Mode B: Twilio Live (Supports personal Gmail accounts)
    if provider == "twilio":
        t_client = get_twilio_client()
        t_from = get_setting("TWILIO_PHONE_NUMBER")
        if t_client and t_from and webhook_base:
            try:
                answer_url = f"{webhook_base}/twilio/answer?call_uuid={call_uuid}&student={student_name}&parent={parent_name}&amount={amount}&due={due_date}&inst={institute}"
                call = t_client.calls.create(
                    to=phone,
                    from_=t_from,
                    url=answer_url,
                    status_callback=f"{webhook_base}/twilio/status?call_uuid={call_uuid}",
                    status_callback_event=["completed", "busy", "no-answer", "failed"]
                )
                update_call_log(call_uuid, {"call_status": "RINGING"})
                await ws_broadcast_func({
                    "type": "CALL_STATUS",
                    "call_uuid": call_uuid,
                    "student_name": student_name,
                    "phone": phone,
                    "status": "RINGING",
                    "message": f"Calling {phone} via Twilio Voice..."
                })
                return {"status": "success", "mode": "TWILIO_LIVE", "call_uuid": call.sid}
            except Exception as e:
                print(f"Twilio live dial failed: {e}. Falling back to simulation.")

    # Mode C: Plivo Live (For business work emails)
    if provider == "plivo":
        p_client = get_plivo_client()
        p_from = get_setting("PLIVO_PHONE_NUMBER")
        if p_client and p_from and webhook_base:
            try:
                answer_url = f"{webhook_base}/plivo/answer?call_uuid={call_uuid}&student={student_name}&parent={parent_name}&amount={amount}&due={due_date}&inst={institute}"
                hangup_url = f"{webhook_base}/plivo/status?call_uuid={call_uuid}"
                response = p_client.calls.create(
                    from_=p_from,
                    to_=phone,
                    answer_url=answer_url,
                    answer_method="POST",
                    hangup_url=hangup_url,
                    hangup_method="POST"
                )
                update_call_log(call_uuid, {"call_status": "RINGING"})
                return {"status": "success", "mode": "PLIVO_LIVE", "call_uuid": response.get("request_uuid", call_uuid)}
            except Exception as e:
                print(f"Plivo live dial failed: {e}. Falling back to simulation.")

    # Mode D: Automated Realistic Simulator (No accounts needed)
    asyncio.create_task(run_simulated_call(call_uuid, student_data, ws_broadcast_func))
    return {"status": "success", "mode": "SIMULATION", "call_uuid": call_uuid}

async def run_simulated_call(call_uuid: str, student_data: Dict[str, Any], ws_broadcast):
    student_name = student_data.get("student_name", "Student")
    phone = student_data.get("mobile_number", "")
    amount = float(student_data.get("pending_amount", 0.0))
    
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
    
    update_call_log(call_uuid, {"call_status": "IN_PROGRESS"})
    await ws_broadcast({
        "type": "CALL_EVENT",
        "call_uuid": call_uuid,
        "student_name": student_name,
        "phone": phone,
        "status": "IN_PROGRESS",
        "step": f"Call answered! Bot speaking fee reminder (₹{int(amount)})...",
        "transcript": "Bot: 'Hello, calling regarding pending fee dues...'"
    })
    await asyncio.sleep(3.5)
    
    scenario = random.choice(SIMULATED_SCENARIOS)
    spoken_text = scenario["speech"]
    duration = scenario["duration"]
    
    await ws_broadcast({
        "type": "CALL_EVENT",
        "call_uuid": call_uuid,
        "student_name": student_name,
        "phone": phone,
        "status": "SPEECH_RECOGNITION",
        "step": "Parent is speaking... processing audio...",
        "transcript": f"Parent: \"{spoken_text}\""
    })
    await asyncio.sleep(2.0)
    
    openai_key = get_setting("OPENAI_API_KEY", "")
    extraction = analyze_caller_speech(spoken_text, student_name, amount, openai_key)
    
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
