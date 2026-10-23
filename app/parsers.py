import io
import re
from typing import List, Dict, Any
import pandas as pd
from pypdf import PdfReader

def normalize_column_name(col: str) -> str:
    cleaned = str(col).strip().lower().replace("_", " ").replace("-", " ")
    if any(k in cleaned for k in ["student name", "student", "candidate", "pupil"]):
        return "student_name"
    if any(k in cleaned for k in ["parent", "father", "mother", "guardian"]):
        return "parent_name"
    if any(k in cleaned for k in ["mobile", "phone", "contact", "cell", "number"]):
        return "mobile_number"
    if any(k in cleaned for k in ["amount", "pending", "fees", "fee", "balance", "due amt"]):
        return "pending_amount"
    if any(k in cleaned for k in ["due date", "deadline", "due on", "last date"]):
        return "due_date"
    if any(k in cleaned for k in ["institute", "school", "academy", "college"]):
        return "institute_name"
    if any(k in cleaned for k in ["course", "class", "grade", "standard", "branch"]):
        return "course_class"
    if any(k in cleaned for k in ["reason", "remark", "notes", "description"]):
        return "reason"
    if any(k in cleaned for k in ["id", "roll", "reg", "enrollment"]):
        return "student_id"
    return cleaned

def clean_phone(phone: Any) -> str:
    if phone is None:
        return ""
    digits = re.sub(r"[^\d+]", "", str(phone))
    if not digits:
        return ""
    if digits.startswith("+"):
        return digits
    if len(digits) == 10:
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    return f"+{digits}"

def clean_amount(val: Any) -> float:
    if val is None:
        return 0.0
    val_str = str(val).replace(",", "").replace("₹", "").replace("Rs", "").replace("$", "").strip()
    try:
        return float(val_str)
    except Exception:
        match = re.search(r"[-+]?\d*\.\d+|\d+", val_str)
        return float(match.group()) if match else 0.0

def parse_excel_or_csv(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    bio = io.BytesIO(file_bytes)
    if filename.lower().endswith(".csv"):
        df = pd.read_csv(bio)
    else:
        df = pd.read_excel(bio)
        
    df = df.dropna(how="all")
    col_map = {col: normalize_column_name(col) for col in df.columns}
    df = df.rename(columns=col_map)
    
    records = []
    for idx, row in df.iterrows():
        # Minimum required: student_name or mobile_number
        student_name = str(row.get("student_name", f"Student {idx+1}")).strip()
        mobile_raw = row.get("mobile_number", "")
        mobile = clean_phone(mobile_raw)
        amount = clean_amount(row.get("pending_amount", 0.0))
        
        if not mobile and not student_name:
            continue
            
        record = {
            "student_id": str(row.get("student_id", f"STU-{1000 + idx}")),
            "student_name": student_name,
            "parent_name": str(row.get("parent_name", "Guardian")).strip(),
            "mobile_number": mobile,
            "pending_amount": amount,
            "due_date": str(row.get("due_date", "2026-10-30")).strip(),
            "institute_name": str(row.get("institute_name", "Apex Learning Academy")).strip(),
            "course_class": str(row.get("course_class", "Grade 10")).strip(),
            "reason": str(row.get("reason", "Term 2 Tuition Fee Overdue")).strip()
        }
        records.append(record)
    return records

def parse_pdf(file_bytes: bytes) -> List[Dict[str, Any]]:
    bio = io.BytesIO(file_bytes)
    reader = PdfReader(bio)
    text = ""
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text += t + "\n"
        
    records = []
    lines = text.split("\n")
    
    phone_pattern = re.compile(r"(\+?91[\s-]?)?[6-9]\d{9}")
    amount_pattern = re.compile(r"(?:Rs\.?|₹|INR)\s*([\d,]+(?:\.\d{2})?)|\b([\d,]{4,}(?:\.\d{2})?)\b")
    date_pattern = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")
    id_pattern = re.compile(r"\b(STU[-\d\w]+|[A-Z]{2,4}[-\d\w]+)\b")
    
    count = 1
    for line in lines:
        line_clean = line.strip()
        # Ignore header rows
        if "student name" in line_clean.lower() or "mobile number" in line_clean.lower() or "confidential" in line_clean.lower():
            continue
            
        phone_match = phone_pattern.search(line_clean)
        if phone_match:
            phone_str = phone_match.group(0)
            phone = clean_phone(phone_str)
            
            # Find date
            date_match = date_pattern.search(line_clean)
            due_date = date_match.group(0) if date_match else "2026-10-30"
            
            # Find amount: prefer Rs./INR/₹ prefixed amount or largest number that isn't the phone
            amount = 0.0
            amt_matches = amount_pattern.findall(line_clean)
            for m in amt_matches:
                val_cand = m[0] or m[1]
                val = clean_amount(val_cand)
                # Ensure it's not the phone number or id number
                if 100 <= val < 10000000 and str(int(val)) not in phone_str:
                    amount = val
                    break
            if amount == 0.0:
                amount = 24500.0
                
            # Extract names before phone number
            prefix = line_clean[:phone_match.start()].strip()
            # Remove student ID from prefix
            id_match = id_pattern.search(prefix)
            student_id = id_match.group(0) if id_match else f"STU-{1000 + count}"
            if id_match:
                prefix = prefix[id_match.end():].strip()
                
            name_parts = [p for p in prefix.split() if len(p) > 1 and not p.isdigit()]
            if len(name_parts) >= 4:
                # E.g. Rohan Patil Ramesh Patil -> Student: Rohan Patil, Parent: Ramesh Patil
                mid = len(name_parts) // 2
                student_name = " ".join(name_parts[:mid])
                parent_name = " ".join(name_parts[mid:])
            elif len(name_parts) >= 2:
                student_name = " ".join(name_parts)
                parent_name = f"Mr. {name_parts[-1]}"
            else:
                student_name = prefix if prefix else f"Student {count}"
                parent_name = f"Parent of {student_name}"
                
            records.append({
                "student_id": student_id,
                "student_name": student_name,
                "parent_name": parent_name,
                "mobile_number": phone,
                "pending_amount": amount,
                "due_date": due_date,
                "institute_name": "Apex Learning Academy",
                "course_class": "Grade 12 - Sci",
                "reason": "Tuition Fee Dues"
            })
            count += 1
            
    return records

def parse_uploaded_file(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    fname = filename.lower()
    if fname.endswith(".csv") or fname.endswith(".xlsx") or fname.endswith(".xls"):
        return parse_excel_or_csv(file_bytes, filename)
    elif fname.endswith(".pdf"):
        return parse_pdf(file_bytes)
    else:
        raise ValueError("Unsupported file format. Please upload .xlsx, .csv, or .pdf")

def get_sample_records() -> List[Dict[str, Any]]:
    return [
        {
            "student_id": "STU-8801",
            "student_name": "Aarav Sharma",
            "parent_name": "Rajesh Sharma",
            "mobile_number": "+919876543210",
            "pending_amount": 18500.0,
            "due_date": "2026-10-15",
            "institute_name": "Apex Learning Academy",
            "course_class": "Grade 11 - Science",
            "reason": "Term 1 Tuition & Lab Fees"
        },
        {
            "student_id": "STU-8802",
            "student_name": "Ananya Patel",
            "parent_name": "Kirit Patel",
            "mobile_number": "+919823456781",
            "pending_amount": 12000.0,
            "due_date": "2026-10-10",
            "institute_name": "Apex Learning Academy",
            "course_class": "Grade 9 - CBSE",
            "reason": "Quarterly Transportation & Tuition"
        },
        {
            "student_id": "STU-8803",
            "student_name": "Rohan Verma",
            "parent_name": "Sunil Verma",
            "mobile_number": "+919712345672",
            "pending_amount": 25000.0,
            "due_date": "2026-10-05",
            "institute_name": "Apex Learning Academy",
            "course_class": "Grade 12 - Commerce",
            "reason": "Annual Development & Exam Fee"
        },
        {
            "student_id": "STU-8804",
            "student_name": "Pooja Deshmukh",
            "parent_name": "Nitin Deshmukh",
            "mobile_number": "+919922334455",
            "pending_amount": 9500.0,
            "due_date": "2026-10-18",
            "institute_name": "Apex Learning Academy",
            "course_class": "Grade 8 - ICSE",
            "reason": "Extracurricular & Activity Fees"
        },
        {
            "student_id": "STU-8805",
            "student_name": "Kabir Mehta",
            "parent_name": "Sanjay Mehta",
            "mobile_number": "+919845098450",
            "pending_amount": 31000.0,
            "due_date": "2026-10-12",
            "institute_name": "Apex Learning Academy",
            "course_class": "JEE Advanced Batch",
            "reason": "Coaching & Test Series Overdue"
        }
    ]
