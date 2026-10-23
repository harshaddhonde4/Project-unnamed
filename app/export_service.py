import io
import os
from typing import List, Dict, Any
import pandas as pd
from app.database import get_dashboard_stats

def generate_excel_export(call_logs: List[Dict[str, Any]]) -> bytes:
    """Generates an Excel workbook with formatted call logs."""
    rows = []
    for log in call_logs:
        rows.append({
            "Call ID": log.get("call_uuid", ""),
            "Student Name": log.get("student_name", ""),
            "Parent Name": log.get("parent_name", ""),
            "Mobile Number": log.get("mobile_number", ""),
            "Pending Amount (INR)": log.get("pending_amount", 0.0),
            "Call Status": log.get("call_status", ""),
            "Outcome / Intent": log.get("outcome", ""),
            "Tentative Pay Date": log.get("tentative_pay_date", "") or "N/A",
            "Call Duration (sec)": log.get("duration", 0),
            "Caller Spoken Response": log.get("raw_transcript", ""),
            "Summary Notes": log.get("summary_notes", ""),
            "Manual Follow-up Required": "YES" if log.get("manual_followup") else "NO",
            "Call Timestamp": log.get("created_at", "")
        })
        
    df = pd.DataFrame(rows)
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Call_Disposition_Audit")
        worksheet = writer.sheets["Call_Disposition_Audit"]
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            worksheet.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)
            
    bio.seek(0)
    return bio.getvalue()

def generate_pdf_summary(call_logs: List[Dict[str, Any]], stats: Dict[str, Any], output_path: str = "/tmp/summary.pdf") -> bytes:
    """Uses the pure Python PDF generator to create an executive PDF report."""
    from build_system_architecture_pdf import PDFDoc
    
    doc = PDFDoc(output_path)
    
    # Title Banner
    doc.rect_fill(doc.margin_x, doc.y - 70, doc.content_w, 70, 0.08, 0.18, 0.36)
    doc.text(doc.margin_x + 15, doc.y - 25, "OUTBOUND FEE COLLECTION CAMPAIGN AUDIT REPORT", font="F2", size=15, r=1, g=1, b=1)
    doc.text(doc.margin_x + 15, doc.y - 45, "Plivo Telephony & Conversational AI Disposition Summary", font="F1", size=10, r=0.85, g=0.92, b=1)
    doc.y -= 85
    
    doc.add_heading2("1. Executive Campaign Performance Metrics")
    stats_headers = ["Metric", "Value", "Metric", "Value"]
    stats_rows = [
        ["Total Dues in Roster", f"Rs. {int(stats.get('total_dues', 0)):,}", "Total Calls Placed", str(stats.get('total_calls', 0))],
        ["Calls Completed", str(stats.get('completed_calls', 0)), "Contact Rate", f"{stats.get('contact_rate', 0)}%"],
        ["Promise to Pay (Count)", str(stats.get('promise_count', 0)), "Promise to Pay (Amount)", f"Rs. {int(stats.get('promise_amount', 0)):,}"],
        ["Already Paid Confirmations", str(stats.get('paid_count', 0)), "Already Paid (Amount)", f"Rs. {int(stats.get('paid_amount', 0)):,}"],
        ["Disputes & Follow-ups", str(stats.get('dispute_count', 0)), "Unreachable / No Answer", str(stats.get('no_answer_count', 0))]
    ]
    doc.add_table(stats_headers, stats_rows, [130, 120, 130, 125])
    
    doc.y -= 8
    doc.add_heading2("2. Detailed Student Call Disposition Log")
    
    table_headers = ["Student Name", "Phone", "Amount", "Outcome", "Tentative Date", "Summary Notes"]
    table_rows = []
    for l in call_logs[:25]: # First 25 calls
        t_date = l.get("tentative_pay_date") or "-"
        notes = l.get("summary_notes", "") or l.get("raw_transcript", "")
        # truncate notes
        if len(notes) > 30:
            notes = notes[:28] + ".."
        table_rows.append([
            l.get("student_name", "")[:14],
            l.get("mobile_number", "")[-10:],
            f"Rs. {int(l.get('pending_amount', 0))}",
            l.get("outcome", "")[:14],
            t_date[:10],
            notes
        ])
        
    if not table_rows:
        table_rows.append(["No calls logged yet", "-", "-", "-", "-", "-"])
        
    doc.add_table(table_headers, table_rows, [85, 75, 65, 85, 75, 120])
    
    doc.build()
    
    with open(output_path, "rb") as f:
        data = f.read()
    return data
