#!/usr/bin/env python3
"""
Launcher for Automated Voice AI Fee Collection System.
Starts the FastAPI server with WebSocket support on port 8000.
"""

import uvicorn
import os
import sys

# Ensure Grok directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import init_db, get_students, insert_students
from app.parsers import get_sample_records

def bootstrap():
    init_db()
    # Populate initial sample records if database is empty
    students = get_students()
    if not students:
        samples = get_sample_records()
        insert_students(samples)
        print(f"[*] Bootstrapped database with {len(samples)} sample student fee records.")

if __name__ == "__main__":
    bootstrap()
    port = int(os.environ.get("PORT", 8000))
    print("=" * 70)
    print("  🚀 APEX VOICE AI - OUTBOUND FEE COLLECTION SYSTEM")
    print("=" * 70)
    print(f"  • Production UI Dashboard: http://localhost:{port}")
    print(f"  • WebSocket Live Stream:   ws://localhost:{port}/ws")
    print(f"  • Plivo Webhook Answer:    http://localhost:{port}/plivo/answer")
    print(f"  • Plivo Webhook Speech:    http://localhost:{port}/plivo/speech")
    print("=" * 70)
    print("  To connect with Plivo live calls, expose port with ngrok:")
    print(f"  $ ngrok http {port}")
    print("=" * 70)
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
