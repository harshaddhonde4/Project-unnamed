import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

def rule_based_extract(speech_text: str, student_name: str, pending_amount: float) -> Dict[str, Any]:
    text = speech_text.lower().strip()
    today = datetime.now()
    
    # 1. First, detect WRONG NUMBER
    wrong_keywords = ["wrong number", "who is this", "wrong person", "galat number", "don't know", "no rahul", "no student", "wrong contact"]
    if any(k in text for k in wrong_keywords):
        return {
            "outcome": "WRONG_NUMBER",
            "tentative_pay_date": None,
            "summary_notes": f"Wrong number indicated. Spoke: '{speech_text}'",
            "manual_followup": 1,
            "bot_reply": "We apologize for the inconvenience. We will update our records and remove this number. Goodbye."
        }
        
    # 2. Detect DISPUTES or INSTALLMENT / EXTENSION requests
    dispute_keywords = ["wrong amount", "scholarship", "excess fees", "discount", "galat amount", "already spoke to principal", "concession"]
    installment_keywords = ["installment", "half now", "salary delayed", "financial problem", "kist", "split"]
    if any(k in text for k in dispute_keywords):
        return {
            "outcome": "DISPUTED",
            "tentative_pay_date": None,
            "summary_notes": f"Fee dispute raised: '{speech_text}'",
            "manual_followup": 1,
            "bot_reply": "Understood. I have recorded your dispute for our accounts department. A finance counselor will reach out to assist you. Goodbye!"
        }
    if any(k in text for k in installment_keywords) and not any(k in text for k in ["already paid", "paid yesterday"]):
        return {
            "outcome": "EXTENSION_REQUEST",
            "tentative_pay_date": None,
            "summary_notes": f"Installment/extension requested: '{speech_text}'",
            "manual_followup": 1,
            "bot_reply": "I have noted your request for fee installment. Our administrative office will call you to arrange the schedule. Goodbye!"
        }

    # 3. Check for FUTURE PAYMENT COMMITMENT & TENTATIVE DATES (Promise to Pay)
    future_pay_intent = any(k in text for k in [
        "will pay", "will give", "will transfer", "will clear", "will deposit",
        "pay by", "pay on", "pay next", "kar dunga", "denge", "bhej dunga", "promise"
    ])
    
    tentative_date = None
    month_names = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
        "nov": 11, "november": 11, "dec": 12, "december": 12
    }
    
    # Check for specific month and day, e.g. "15th of november" or "november 15"
    month_match = re.search(r"(?:on|by)?\s*(\d{1,2})(?:st|nd|rd|th)?\s*(?:of)?\s*(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)", text)
    if not month_match:
        month_match = re.search(r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s*(\d{1,2})(?:st|nd|rd|th)?", text)
        if month_match:
            m_name, d_str = month_match.group(1), month_match.group(2)
        else:
            m_name, d_str = None, None
    else:
        d_str, m_name = month_match.group(1), month_match.group(2)
        
    if m_name and d_str:
        m_num = month_names.get(m_name[:3], today.month)
        d_num = int(d_str)
        y_num = today.year if m_num >= today.month else today.year + 1
        tentative_date = f"{y_num:04d}-{m_num:02d}-{d_num:02d}"
    elif "tomorrow" in text or "kal" in text:
        tentative_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "next week" in text or "agle hafte" in text or "next monday" in text:
        tentative_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
    elif "next month" in text or "agle mahine" in text:
        tentative_date = (today + timedelta(days=30)).strftime("%Y-%m-%d")
    else:
        day_match = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)\b", text)
        if day_match:
            day = int(day_match.group(1))
            if 1 <= day <= 31:
                target_month = today.month if day > today.day else (today.month % 12 + 1)
                target_year = today.year if (day > today.day or today.month < 12) else today.year + 1
                tentative_date = f"{target_year:04d}-{target_month:02d}-{day:02d}"

    # If future payment intent is stated or date is found:
    if future_pay_intent or (tentative_date and not any(k in text for k in ["already paid", "paid yesterday"])):
        disp_date = tentative_date or (today + timedelta(days=5)).strftime("%Y-%m-%d")
        return {
            "outcome": "PROMISE_TO_PAY",
            "tentative_pay_date": disp_date,
            "summary_notes": f"Promised to pay on or by {disp_date}. Spoke: '{speech_text}'",
            "manual_followup": 0,
            "bot_reply": f"Thank you. We have recorded your tentative payment date as {disp_date}. Please ensure it is cleared by then. Have a wonderful day!"
        }

    # 4. Check for ALREADY PAID (Past tense confirmation)
    paid_keywords = [
        "already paid", "paid yesterday", "done payment", "cleared", "paid online",
        "already transferred", "paid through gpay", "paid through google pay",
        "paid last week", "paid today", "already done", "maine pay kar diya",
        "maine bhar diya", "bhej diya", "already settled", "already given"
    ]
    if any(k in text for k in paid_keywords):
        return {
            "outcome": "ALREADY_PAID",
            "tentative_pay_date": None,
            "summary_notes": f"Caller stated fee was already paid. Spoke: '{speech_text}'",
            "manual_followup": 0,
            "bot_reply": "Thank you for letting us know. We will verify your transaction with our accounts desk. You may ignore this reminder. Have a great day!"
        }
        
    # Default fallback: Unclear response
    return {
        "outcome": "UNCLEAR",
        "tentative_pay_date": None,
        "summary_notes": f"Unclear response: '{speech_text}'",
        "manual_followup": 1,
        "bot_reply": "Thank you. We have noted your response and our administrative staff will follow up with you. Goodbye!"
    }

def analyze_caller_speech(speech_text: str, student_name: str, pending_amount: float, api_key: str = "") -> Dict[str, Any]:
    if not speech_text or len(speech_text.strip()) == 0:
        return {
            "outcome": "UNREACHABLE",
            "tentative_pay_date": None,
            "summary_notes": "No voice response heard during call.",
            "manual_followup": 1,
            "bot_reply": "We did not receive any response. We will follow up later. Thank you."
        }

    # Import get_setting safely to check DB settings
    try:
        from app.database import get_setting
        db_groq_key = get_setting("GROQ_API_KEY", "")
        db_openai_key = get_setting("OPENAI_API_KEY", "")
    except Exception:
        db_groq_key = ""
        db_openai_key = ""

    groq_key = os.getenv("GROQ_API_KEY") or db_groq_key or (api_key if api_key.startswith("gsk_") else "")
    openai_key = api_key or os.getenv("OPENAI_API_KEY") or db_openai_key

    today_str = datetime.now().strftime("%Y-%m-%d, %A")

    # 1. Try Groq Cloud (Ultra-Fast LPU Inference)
    if groq_key and len(groq_key.strip()) > 10:
        try:
            import requests, json
            headers = {
                "Authorization": f"Bearer {groq_key.strip()}",
                "Content-Type": "application/json"
            }
            prompt = (
                f"You are a fee collection conversational intent analyzer for an educational institute.\n"
                f"Today's Date: {today_str}.\n"
                f"Student: {student_name}, Pending Amount: Rs. {pending_amount}.\n"
                f"Caller spoke: '{speech_text}'.\n\n"
                f"Extract in JSON with keys:\n"
                f"- outcome: exactly one of ['ALREADY_PAID', 'PROMISE_TO_PAY', 'EXTENSION_REQUEST', 'DISPUTED', 'WRONG_NUMBER', 'UNCLEAR']\n"
                f"- tentative_pay_date: 'YYYY-MM-DD' (calculate exact date relative to Today {today_str}) or null\n"
                f"- summary_notes: concise 1-sentence note stating intent, date, and payment method if mentioned\n"
                f"- manual_followup: true or false\n"
                f"- bot_reply: polite, short closing statement acknowledging caller's specific reply."
            )
            
            # Supported Groq models in order of priority
            models = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
            for model_name in models:
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": "You are a professional payment analytics assistant. Return valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1
                }
                res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=8)
                if res.status_code == 200:
                    data = res.json()["choices"][0]["message"]["content"]
                    parsed = json.loads(data)
                    return {
                        "outcome": parsed.get("outcome", "UNCLEAR"),
                        "tentative_pay_date": parsed.get("tentative_pay_date"),
                        "summary_notes": parsed.get("summary_notes", speech_text),
                        "manual_followup": 1 if parsed.get("manual_followup") else 0,
                        "bot_reply": parsed.get("bot_reply", "Thank you. We have recorded your response. Goodbye!"),
                        "engine": f"Groq ({model_name})"
                    }
        except Exception as e:
            print(f"Groq API call error: {e}. Trying secondary LLM / fallback...")

    # 2. Try OpenAI if configured
    if openai_key and len(openai_key.strip()) > 10:
        try:
            import requests, json
            headers = {
                "Authorization": f"Bearer {openai_key.strip()}",
                "Content-Type": "application/json"
            }
            prompt = (
                f"You are a fee collection intent analyzer for an educational institute.\n"
                f"Today's Date: {today_str}.\n"
                f"Student: {student_name}, Pending Amount: Rs. {pending_amount}.\n"
                f"Caller spoke: '{speech_text}'.\n\n"
                f"Extract in JSON with keys:\n"
                f"- outcome: exactly one of ['ALREADY_PAID', 'PROMISE_TO_PAY', 'EXTENSION_REQUEST', 'DISPUTED', 'WRONG_NUMBER', 'UNCLEAR']\n"
                f"- tentative_pay_date: 'YYYY-MM-DD' or null\n"
                f"- summary_notes: concise 1-sentence note\n"
                f"- manual_followup: true or false\n"
                f"- bot_reply: polite, short closing statement acknowledging caller's specific reply."
            )
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are a professional payment analytics assistant. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1
            }
            res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=6)
            if res.status_code == 200:
                data = res.json()["choices"][0]["message"]["content"]
                parsed = json.loads(data)
                return {
                    "outcome": parsed.get("outcome", "UNCLEAR"),
                    "tentative_pay_date": parsed.get("tentative_pay_date"),
                    "summary_notes": parsed.get("summary_notes", speech_text),
                    "manual_followup": 1 if parsed.get("manual_followup") else 0,
                    "bot_reply": parsed.get("bot_reply", "Thank you. We have recorded your response. Goodbye!"),
                    "engine": "OpenAI (gpt-4o-mini)"
                }
        except Exception as e:
            print(f"OpenAI API call failed, falling back to rule-based: {e}")

    # 3. Fallback to smart rule-based NLP analyzer
    fallback_res = rule_based_extract(speech_text, student_name, pending_amount)
    fallback_res["engine"] = "Rule-based NLP"
    return fallback_res
