import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "voice_system.db")

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Students / Dues table
    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            student_name TEXT NOT NULL,
            parent_name TEXT,
            mobile_number TEXT NOT NULL,
            pending_amount REAL NOT NULL,
            due_date TEXT,
            institute_name TEXT DEFAULT 'Apex Learning Academy',
            course_class TEXT,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Call logs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS call_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_uuid TEXT UNIQUE,
            student_id TEXT,
            student_name TEXT NOT NULL,
            parent_name TEXT,
            mobile_number TEXT NOT NULL,
            pending_amount REAL NOT NULL,
            call_status TEXT DEFAULT 'QUEUED', 
            outcome TEXT DEFAULT 'PENDING',
            tentative_pay_date TEXT,
            raw_transcript TEXT,
            bot_response TEXT,
            summary_notes TEXT,
            manual_followup INTEGER DEFAULT 0,
            duration INTEGER DEFAULT 0,
            recording_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Settings table
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Default settings if empty
    defaults = {
        "TELEPHONY_PROVIDER": "browser",  # 'browser' (no signup needed), 'twilio' (personal gmail), 'plivo', 'simulation'
        "TWILIO_ACCOUNT_SID": "",
        "TWILIO_AUTH_TOKEN": "",
        "TWILIO_PHONE_NUMBER": "",
        "PLIVO_AUTH_ID": "",
        "PLIVO_AUTH_TOKEN": "",
        "PLIVO_PHONE_NUMBER": "",
        "PUBLIC_WEBHOOK_URL": "",
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "CALLING_THROTTLE_SECONDS": "5"
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        
    conn.commit()
    conn.close()

# Settings Helpers
def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row["value"] if row and row["value"] is not None else default

def set_setting(key: str, value: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_all_settings() -> Dict[str, str]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT key, value FROM settings")
    rows = c.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}

# Students Helpers
def insert_students(student_list: List[Dict[str, Any]]):
    conn = get_connection()
    c = conn.cursor()
    for s in student_list:
        c.execute('''
            INSERT INTO students (
                student_id, student_name, parent_name, mobile_number, 
                pending_amount, due_date, institute_name, course_class, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            s.get("student_id", ""),
            s.get("student_name", "Unknown"),
            s.get("parent_name", ""),
            s.get("mobile_number", ""),
            float(s.get("pending_amount", 0.0)),
            s.get("due_date", ""),
            s.get("institute_name", "Apex Learning Academy"),
            s.get("course_class", ""),
            s.get("reason", "Tuition Fee Dues")
        ))
    conn.commit()
    conn.close()

def get_students() -> List[Dict[str, Any]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM students ORDER BY id DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def clear_students():
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM students")
    conn.commit()
    conn.close()

# Call Logs Helpers
def create_call_log(data: Dict[str, Any]) -> str:
    conn = get_connection()
    c = conn.cursor()
    call_uuid = data.get("call_uuid", f"call-{int(datetime.now().timestamp() * 1000)}")
    c.execute('''
        INSERT OR REPLACE INTO call_logs (
            call_uuid, student_id, student_name, parent_name, mobile_number,
            pending_amount, call_status, outcome, tentative_pay_date,
            raw_transcript, bot_response, summary_notes, manual_followup, duration, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (
        call_uuid,
        data.get("student_id", ""),
        data.get("student_name", ""),
        data.get("parent_name", ""),
        data.get("mobile_number", ""),
        float(data.get("pending_amount", 0.0)),
        data.get("call_status", "QUEUED"),
        data.get("outcome", "PENDING"),
        data.get("tentative_pay_date", ""),
        data.get("raw_transcript", ""),
        data.get("bot_response", ""),
        data.get("summary_notes", ""),
        data.get("manual_followup", 0),
        data.get("duration", 0)
    ))
    conn.commit()
    conn.close()
    return call_uuid

def update_call_log(call_uuid: str, updates: Dict[str, Any]):
    conn = get_connection()
    c = conn.cursor()
    fields = []
    values = []
    for k, v in updates.items():
        fields.append(f"{k} = ?")
        values.append(v)
    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(call_uuid)
    
    query = f"UPDATE call_logs SET {', '.join(fields)} WHERE call_uuid = ?"
    c.execute(query, values)
    conn.commit()
    conn.close()

def get_call_logs(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM call_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_call_by_uuid(call_uuid: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM call_logs WHERE call_uuid = ?", (call_uuid,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def toggle_manual_followup(call_uuid: str) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT manual_followup FROM call_logs WHERE call_uuid = ?", (call_uuid,))
    row = c.fetchone()
    if row:
        new_val = 0 if row["manual_followup"] else 1
        c.execute("UPDATE call_logs SET manual_followup = ? WHERE call_uuid = ?", (new_val, call_uuid))
        conn.commit()
        conn.close()
        return new_val
    conn.close()
    return 0

# Stats calculation
def get_dashboard_stats() -> Dict[str, Any]:
    conn = get_connection()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) as total_students, COALESCE(SUM(pending_amount), 0) as total_dues FROM students")
    s_row = c.fetchone()
    total_students = s_row["total_students"] or 0
    total_dues = s_row["total_dues"] or 0.0
    
    c.execute("SELECT COUNT(*) as total_calls FROM call_logs")
    total_calls = c.fetchone()["total_calls"] or 0
    
    c.execute("SELECT COUNT(*) as completed_calls FROM call_logs WHERE call_status = 'COMPLETED'")
    completed_calls = c.fetchone()["completed_calls"] or 0
    
    c.execute("SELECT COUNT(*) as promise_count, COALESCE(SUM(pending_amount), 0) as promise_amount FROM call_logs WHERE outcome = 'PROMISE_TO_PAY'")
    p_row = c.fetchone()
    promise_count = p_row["promise_count"] or 0
    promise_amount = p_row["promise_amount"] or 0.0
    
    c.execute("SELECT COUNT(*) as paid_count, COALESCE(SUM(pending_amount), 0) as paid_amount FROM call_logs WHERE outcome = 'ALREADY_PAID'")
    paid_row = c.fetchone()
    paid_count = paid_row["paid_count"] or 0
    paid_amount = paid_row["paid_amount"] or 0.0
    
    c.execute("SELECT COUNT(*) as dispute_count FROM call_logs WHERE outcome IN ('DISPUTED', 'EXTENSION_REQUEST') OR manual_followup = 1")
    dispute_count = c.fetchone()["dispute_count"] or 0
    
    c.execute("SELECT COUNT(*) as no_answer_count FROM call_logs WHERE call_status IN ('NO_ANSWER', 'BUSY', 'FAILED', 'TIMEOUT')")
    no_answer_count = c.fetchone()["no_answer_count"] or 0
    
    conn.close()
    
    contact_rate = round((completed_calls / total_calls * 100), 1) if total_calls > 0 else 0.0
    
    return {
        "total_students": total_students,
        "total_dues": total_dues,
        "total_calls": total_calls,
        "completed_calls": completed_calls,
        "contact_rate": contact_rate,
        "promise_count": promise_count,
        "promise_amount": promise_amount,
        "paid_count": paid_count,
        "paid_amount": paid_amount,
        "dispute_count": dispute_count,
        "no_answer_count": no_answer_count
    }
