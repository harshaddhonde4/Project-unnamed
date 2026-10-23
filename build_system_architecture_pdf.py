#!/usr/bin/env python3
"""
Automated Voice AI Fee Collection System - Architecture & Working Specification
Generates a comprehensive, publication-quality PDF technical document.
Pure Python implementation with no external library dependencies.
"""

import sys
import os
import re

class PDFDoc:
    def __init__(self, filename="AUTOMATED_VOICE_AI_FEE_COLLECTION_SYSTEM_SPECIFICATION.pdf"):
        self.filename = filename
        self.pages = []
        self.current_commands = []
        
        # Dimensions for A4: 595.28 x 841.89 points
        self.page_w = 595.28
        self.page_h = 841.89
        self.margin_x = 45.0
        self.margin_top = 50.0
        self.margin_bottom = 50.0
        self.content_w = self.page_w - (2 * self.margin_x) # 505.28 pt
        
        # Cursor tracking
        self.y = self.page_h - self.margin_top
        
    def add_page(self):
        if self.current_commands:
            self.pages.append(self.current_commands)
            self.current_commands = []
        self.y = self.page_h - self.margin_top
        
    def escape_text(self, text):
        # Sanitize common Unicode characters to standard ASCII / WinAnsi
        text = text.replace('\u2022', '-')
        text = text.replace('\u2013', '-')
        text = text.replace('\u2014', '--')
        text = text.replace('\u2018', "'").replace('\u2019', "'")
        text = text.replace('\u201c', '"').replace('\u201d', '"')
        text = text.replace('•', '-')
        # Encode non-ascii as ascii replacements
        text = text.encode('ascii', 'replace').decode('ascii')
        return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        
    def set_color_fill(self, r, g, b):
        self.current_commands.append(f"{r:.3f} {g:.3f} {b:.3f} rg")
        
    def set_color_stroke(self, r, g, b):
        self.current_commands.append(f"{r:.3f} {g:.3f} {b:.3f} RG")
        
    def set_line_width(self, w):
        self.current_commands.append(f"{w:.2f} w")
        
    def rect_fill(self, x, y, w, h, r, g, b):
        self.set_color_fill(r, g, b)
        self.current_commands.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")
        
    def rect_stroke(self, x, y, w, h, r, g, b, lw=1.0):
        self.set_color_stroke(r, g, b)
        self.set_line_width(lw)
        self.current_commands.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re s")

    def draw_line(self, x1, y1, x2, y2, r, g, b, lw=1.0):
        self.set_color_stroke(r, g, b)
        self.set_line_width(lw)
        self.current_commands.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l s")
        
    def text(self, x, y, text_str, font="F1", size=10, r=0.1, g=0.1, b=0.1):
        clean_text = self.escape_text(text_str)
        self.set_color_fill(r, g, b)
        cmd = f"BT /{font} {size:.1f} Tf {x:.2f} {y:.2f} Td ({clean_text}) Tj ET"
        self.current_commands.append(cmd)

    def check_page_break(self, needed_height):
        if (self.y - needed_height) < self.margin_bottom:
            self.add_page()
            return True
        return False

    def calc_char_width(self, char, font, size):
        if font in ("F3", "F4"):  # Courier fixed width
            return size * 0.60
        if font == "F2":  # Helvetica-Bold
            return size * 0.55
        # Helvetica regular
        return size * 0.50

    def wrap_text(self, text_str, font, size, max_width):
        words = text_str.split(' ')
        lines = []
        cur_line = []
        cur_w = 0.0
        space_w = self.calc_char_width(' ', font, size)
        
        for w in words:
            word_w = sum(self.calc_char_width(c, font, size) for c in w)
            if cur_line and (cur_w + space_w + word_w > max_width):
                lines.append(' '.join(cur_line))
                cur_line = [w]
                cur_w = word_w
            else:
                if cur_line:
                    cur_w += space_w + word_w
                else:
                    cur_w = word_w
                cur_line.append(w)
        if cur_line:
            lines.append(' '.join(cur_line))
        return lines

    def add_heading1(self, text_str):
        self.check_page_break(45)
        self.y -= 10
        # Accent bar
        self.rect_fill(self.margin_x, self.y - 4, 4, 18, 0.08, 0.22, 0.45) # Deep navy
        self.text(self.margin_x + 10, self.y, text_str, font="F2", size=15, r=0.08, g=0.22, b=0.45)
        self.draw_line(self.margin_x, self.y - 8, self.margin_x + self.content_w, self.y - 8, 0.82, 0.85, 0.90, lw=1.0)
        self.y -= 22

    def add_heading2(self, text_str):
        self.check_page_break(32)
        self.y -= 6
        self.text(self.margin_x, self.y, text_str, font="F2", size=12, r=0.15, g=0.35, b=0.60)
        self.y -= 16

    def add_heading3(self, text_str):
        self.check_page_break(24)
        self.y -= 4
        self.text(self.margin_x, self.y, text_str, font="F2", size=10.5, r=0.2, g=0.25, b=0.3)
        self.y -= 14

    def add_paragraph(self, text_str, font="F1", size=9.5, r=0.15, g=0.18, b=0.22, line_spacing=13.5):
        lines = self.wrap_text(text_str, font, size, self.content_w)
        for line in lines:
            self.check_page_break(line_spacing)
            self.text(self.margin_x, self.y, line, font=font, size=size, r=r, g=g, b=b)
            self.y -= line_spacing
        self.y -= 4

    def add_bullet(self, title_str, text_str, line_spacing=13.0):
        prefix = "•  " + title_str + (" " if title_str else "")
        full_text = prefix + text_str
        lines = self.wrap_text(full_text, "F1", 9.2, self.content_w - 12)
        
        self.check_page_break(len(lines) * line_spacing + 4)
        for i, line in enumerate(lines):
            indent = self.margin_x + 10
            if i == 0 and title_str:
                # We can print title part in bold if wanted, or just clean uniform text
                self.text(indent, self.y, line, font="F1", size=9.2, r=0.15, g=0.18, b=0.22)
            else:
                self.text(indent, self.y, line, font="F1", size=9.2, r=0.15, g=0.18, b=0.22)
            self.y -= line_spacing
        self.y -= 2

    def add_card(self, title, items, r_border=0.15, g_border=0.35, b_border=0.60):
        # Calculate height needed
        calc_h = 24 + len(items) * 14 + 6
        self.check_page_break(calc_h)
        card_top = self.y
        card_h = calc_h
        
        # BG fill
        self.rect_fill(self.margin_x, card_top - card_h + 8, self.content_w, card_h, 0.96, 0.97, 0.99)
        # Left accent stripe
        self.rect_fill(self.margin_x, card_top - card_h + 8, 4, card_h, r_border, g_border, b_border)
        # Border
        self.rect_stroke(self.margin_x, card_top - card_h + 8, self.content_w, card_h, 0.85, 0.88, 0.92, lw=0.7)
        
        # Content
        cur_y = card_top - 10
        self.text(self.margin_x + 12, cur_y, title, font="F2", size=10, r=r_border, g=g_border, b=b_border)
        cur_y -= 14
        
        for item in items:
            self.text(self.margin_x + 14, cur_y, f"• {item}", font="F1", size=8.8, r=0.2, g=0.22, b=0.25)
            cur_y -= 13.5
            
        self.y = card_top - card_h - 2

    def add_code_block(self, code_lines, title=None):
        line_h = 11.5
        box_h = len(code_lines) * line_h + (18 if title else 10)
        self.check_page_break(box_h + 8)
        
        top_y = self.y
        # Box BG
        self.rect_fill(self.margin_x, top_y - box_h + 4, self.content_w, box_h, 0.94, 0.95, 0.97)
        self.rect_stroke(self.margin_x, top_y - box_h + 4, self.content_w, box_h, 0.80, 0.83, 0.87, lw=0.8)
        
        cur_y = top_y - 8
        if title:
            self.text(self.margin_x + 10, cur_y, title, font="F4", size=8.5, r=0.1, g=0.3, b=0.55)
            self.draw_line(self.margin_x, cur_y - 4, self.margin_x + self.content_w, cur_y - 4, 0.82, 0.85, 0.88, lw=0.5)
            cur_y -= 12
            
        for cl in code_lines:
            self.text(self.margin_x + 10, cur_y, cl, font="F3", size=8.0, r=0.12, g=0.15, b=0.20)
            cur_y -= line_h
            
        self.y = top_y - box_h - 4

    def add_table(self, headers, rows, col_widths):
        # headers: list of str
        # rows: list of list of str
        # col_widths: list of float summing to <= self.content_w
        header_h = 18.0
        row_h = 16.0
        total_h = header_h + len(rows) * row_h
        
        self.check_page_break(total_h + 10)
        table_top = self.y
        
        # Header background
        self.rect_fill(self.margin_x, table_top - header_h, self.content_w, header_h, 0.10, 0.22, 0.42)
        
        # Header text
        cur_x = self.margin_x
        for i, h in enumerate(headers):
            self.text(cur_x + 5, table_top - 12, h, font="F2", size=8.5, r=1.0, g=1.0, b=1.0)
            cur_x += col_widths[i]
            
        # Rows
        cur_y = table_top - header_h
        for row_idx, r in enumerate(rows):
            # Alternating row color
            if row_idx % 2 == 1:
                self.rect_fill(self.margin_x, cur_y - row_h, self.content_w, row_h, 0.96, 0.97, 0.98)
            else:
                self.rect_fill(self.margin_x, cur_y - row_h, self.content_w, row_h, 1.0, 1.0, 1.0)
                
            cur_x = self.margin_x
            for col_idx, cell in enumerate(r):
                # Clean truncate or fit
                cell_str = str(cell)
                self.text(cur_x + 5, cur_y - 11.5, cell_str, font="F1", size=8.2, r=0.18, g=0.20, b=0.25)
                cur_x += col_widths[col_idx]
                
            # Row border
            self.draw_line(self.margin_x, cur_y - row_h, self.margin_x + self.content_w, cur_y - row_h, 0.85, 0.88, 0.90, lw=0.5)
            cur_y -= row_h
            
        # Outer table border
        self.rect_stroke(self.margin_x, table_top - total_h, self.content_w, total_h, 0.75, 0.80, 0.85, lw=0.8)
        self.y = table_top - total_h - 10

    def draw_decorations_and_footers(self):
        total_pages = len(self.pages)
        for page_idx in range(total_pages):
            cmds = self.pages[page_idx]
            page_num = page_idx + 1
            
            # Header (pages > 1)
            if page_num > 1:
                header_text = self.escape_text("Automated Voice AI Outbound Fee Collection System | Technical Architecture")
                cmds.append(f"BT /F1 7.5 Tf {self.margin_x:.2f} {self.page_h - 32:.2f} Td 0.45 0.50 0.55 rg ({header_text}) Tj ET")
                # Top thin divider
                cmds.append(f"0.85 0.88 0.92 RG 0.5 w {self.margin_x:.2f} {self.page_h - 36:.2f} m {self.page_w - self.margin_x:.2f} {self.page_h - 36:.2f} l s")
                
            # Footer (all pages)
            footer_left = self.escape_text("CONFIDENTIAL & PROPRIETARY | AI VOICE CAMPAIGN ARCHITECTURE SPECIFICATION")
            footer_right = self.escape_text(f"Page {page_num} of {total_pages}")
            
            # Bottom divider
            cmds.append(f"0.85 0.88 0.92 RG 0.5 w {self.margin_x:.2f} 36.00 m {self.page_w - self.margin_x:.2f} 36.00 l s")
            cmds.append(f"BT /F1 7.5 Tf {self.margin_x:.2f} 25.00 Td 0.45 0.50 0.55 rg ({footer_left}) Tj ET")
            cmds.append(f"BT /F2 7.5 Tf {self.page_w - self.margin_x - 55:.2f} 25.00 Td 0.30 0.35 0.40 rg ({footer_right}) Tj ET")

    def build(self):
        # Save last page
        if self.current_commands:
            self.pages.append(self.current_commands)
            self.current_commands = []
            
        self.draw_decorations_and_footers()
        
        num_pages = len(self.pages)
        page_obj_ids = []
        content_obj_ids = []
        
        # 1: Catalog
        # 2: Pages
        # 3: F1 (Helvetica)
        # 4: F2 (Helvetica-Bold)
        # 5: F3 (Courier)
        # 6: F4 (Courier-Bold)
        cur_id = 7
        for _ in range(num_pages):
            page_obj_ids.append(cur_id)
            cur_id += 1
            content_obj_ids.append(cur_id)
            cur_id += 1
            
        objs = {}
        objs[1] = '<< /Type /Catalog /Pages 2 0 R >>'
        kids_str = ' '.join(f'{pid} 0 R' for pid in page_obj_ids)
        objs[2] = f'<< /Type /Pages /Kids [{kids_str}] /Count {num_pages} >>'
        objs[3] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'
        objs[4] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>'
        objs[5] = '<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>'
        objs[6] = '<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold >>'
        
        for i in range(num_pages):
            pid = page_obj_ids[i]
            cid = content_obj_ids[i]
            objs[pid] = f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.28 841.89] /Contents {cid} 0 R /Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R /F4 6 0 R >> >> >>'
            stream_data = '\n'.join(self.pages[i]).encode('latin1')
            objs[cid] = f'<< /Length {len(stream_data)} >>\nstream\n{stream_data.decode("latin1")}\nendstream'
            
        out = ['%PDF-1.4\n']
        offsets = {}
        curr_offset = len(out[0].encode('latin1'))
        
        max_id = max(objs.keys())
        for oid in range(1, max_id + 1):
            offsets[oid] = curr_offset
            body = f'{oid} 0 obj\n{objs[oid]}\nendobj\n'
            out.append(body)
            curr_offset += len(body.encode('latin1'))
            
        xref_offset = curr_offset
        out.append(f'xref\n0 {max_id + 1}\n0000000000 65535 f \n')
        for oid in range(1, max_id + 1):
            out.append(f'{offsets[oid]:010d} 00000 n \n')
            
        out.append(f'trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n')
        
        with open(self.filename, 'wb') as f:
            f.write(''.join(out).encode('latin1'))
            
        print(f"Generated PDF: {self.filename} ({num_pages} pages, {os.path.getsize(self.filename):,} bytes)")

def create_specification_document(output_pdf_path):
    doc = PDFDoc(output_pdf_path)
    
    # =========================================================================
    # PAGE 1: COVER PAGE & EXECUTIVE OVERVIEW
    # =========================================================================
    # Top decorative header block
    doc.rect_fill(doc.margin_x, doc.y - 120, doc.content_w, 120, 0.08, 0.18, 0.36) # Navy
    doc.rect_fill(doc.margin_x, doc.y - 124, doc.content_w, 4, 0.22, 0.55, 0.85)   # Light blue stripe
    
    doc.text(doc.margin_x + 20, doc.y - 30, "ENTERPRISE TECHNICAL ARCHITECTURE & WORKING SPECIFICATION", font="F2", size=9, r=0.75, g=0.88, b=1.0)
    doc.text(doc.margin_x + 20, doc.y - 58, "Automated Voice AI Outbound Fee Collection System", font="F2", size=18, r=1.0, g=1.0, b=1.0)
    doc.text(doc.margin_x + 20, doc.y - 82, "Autonomous Outbound Dialer, Conversational Voice Bot & Disposition Reporting", font="F1", size=10.5, r=0.85, g=0.92, b=1.0)
    doc.text(doc.margin_x + 20, doc.y - 104, "Dataset Ingestion (Excel/PDF) -> Telephony (Twilio/Plivo/Exotel) -> LLM Reasoning -> Structured Output", font="F1", size=8.5, r=0.70, g=0.82, b=0.95)
    
    doc.y -= 140
    
    # Metadata info bar
    doc.rect_fill(doc.margin_x, doc.y - 32, doc.content_w, 32, 0.95, 0.96, 0.98)
    doc.rect_stroke(doc.margin_x, doc.y - 32, doc.content_w, 32, 0.82, 0.86, 0.90, lw=0.6)
    doc.text(doc.margin_x + 12, doc.y - 14, "Target Domain: Educational Institutes / Universities / EdTech", font="F2", size=8.5, r=0.15, g=0.25, b=0.40)
    doc.text(doc.margin_x + 12, doc.y - 25, "Status: Production-Grade System Architecture Blueprint", font="F1", size=8.0, r=0.35, g=0.40, b=0.45)
    doc.text(doc.margin_x + 350, doc.y - 14, "Architecture Version: 1.0 (Q4 2026)", font="F2", size=8.5, r=0.15, g=0.25, b=0.40)
    doc.text(doc.margin_x + 350, doc.y - 25, "Telephony: Twilio / Plivo / Exotel", font="F1", size=8.0, r=0.35, g=0.40, b=0.45)
    
    doc.y -= 44
    
    doc.add_heading1("1. Executive Summary & Problem Definition")
    doc.add_paragraph(
        "Educational institutions, coaching academies, colleges, and schools face substantial operational friction in "
        "recovering overdue student tuition and term fees. Traditional collection relies on manual phone calls placed by "
        "front-office staff or accountants. This traditional approach suffers from high overhead, low dial volumes (an agent "
        "manages only 40-60 calls/day), lack of real-time structured data recording, and irregular follow-ups."
    )
    doc.add_paragraph(
        "The proposed system solves this challenge end-to-end: it accepts tabular fee rosters from Excel spreadsheets or "
        "PDF ledger reports, parses parent and student records, and triggers automated, high-fidelity conversational voice calls. "
        "The voice agent states the pending balance and due date, requests a tentative payment date, or acknowledges prior payments. "
        "Responses are transcribed, parsed via LLM structured outputs into discrete schemas, and exported as updated spreadsheets "
        "and executive audit reports."
    )
    
    doc.add_card("Core High-Level System Capabilities", [
        "Multi-Format Data Ingestion: Automated extraction from Excel (.xlsx, .csv) and PDF fee dues tables.",
        "Programmatic Outbound Calling: High-throughput batch dialer supporting Twilio, Plivo, and Exotel.",
        "Human-Grade Spoken Conversation: Indian-accented English, Hindi, or bilingual natural language comprehension.",
        "Real-Time Speech Understanding: Fast STT + LLM reasoning for date entity extraction, disputes, and excuses.",
        "Automated Edge-Case Resolution: Handles answering machines, busy signals, wrong numbers, and installments.",
        "Closed-Loop Output Generation: Real-time database logging, updated Excel record generation, and summary PDF exports."
    ], r_border=0.08, g_border=0.22, b_border=0.45)
    
    doc.y -= 6
    doc.add_heading2("System High-Level Metrics & Targets")
    metrics_headers = ["Metric / KPI", "Industry Benchmark (Manual)", "AI Voice System Target", "Operational Impact"]
    metrics_rows = [
        ["Dialing Speed", "35 - 50 calls / staff / day", "500 - 5,000+ calls / hour", "100x throughput multiplier"],
        ["Average Cost Per Call", "Rs. 25.00 - Rs. 40.00 (Staff labor)", "Rs. 1.20 - Rs. 2.50 (Telephony+AI)", "90%+ cost reduction"],
        ["Intent Extraction Accuracy", "60-70% (Subjective notes)", "94% - 98% (Structured LLM)", "Uniform audit-ready records"],
        ["Follow-Up Latency", "2 - 5 days manual delay", "Instant (Within 10 seconds)", "Zero lag in accounts ledger"]
    ]
    doc.add_table(metrics_headers, metrics_rows, [110, 130, 130, 135])
    
    # =========================================================================
    # PAGE 2: COMPLETE ARCHITECTURE & 5-TIER TOPOLOGY
    # =========================================================================
    doc.add_page()
    doc.add_heading1("2. System Architecture & Component Decomposition")
    doc.add_paragraph(
        "The system follows an event-driven, decoupled microservices architecture divided into five distinct operational tiers. "
        "This separation guarantees modularity, allowing independent scaling of telephony workers, LLM reasoning pipelines, "
        "and data export jobs without resource contention."
    )
    
    doc.add_code_block([
        "+---------------------------------------------------------------------------------------------------+",
        "|                                     SYSTEM ARCHITECTURE TOPOLOGY                                  |",
        "+---------------------------------------------------------------------------------------------------+",
        " [INPUT FILES]            [ORCHESTRATION]                [TELEPHONY GATEWAY]        [VOICE AI CORE]  ",
        "  - Excel (.xlsx)   -->    FastAPI Server     --REST-->   Twilio / Exotel     <-->   Deepgram (STT)   ",
        "  - PDF Ledgers     -->    Redis Task Queue               SIP / WebSockets           GPT-4o / Llama-3 ",
        "  - CRM Webhooks    -->    Campaign Dispatch              TwiML Stream / AMD         ElevenLabs (TTS) ",
        "+---------------------------------------------------------------------------------------------------+",
        "                                                 |                                                  ",
        "                                                 v (Post-Call Webhook & Transcript)                 ",
        " [EXTRACTION & DISPOSITION]               [DATA PERSISTENCE]                [OUTPUT & REPORTING]    ",
        "  - Pydantic Extractor              -->    PostgreSQL / SQLite         -->   Updated Excel (.xlsx)  ",
        "  - Intent & Date Normalizer               Audit Event Logs                  Executive PDF Summary  ",
        "  - Flag Manual Review Queue               Call Recording Audio              Accounts Webhook Push  ",
        "+---------------------------------------------------------------------------------------------------+"
    ], title="Fig 1: End-to-End System Block Diagram")
    
    doc.add_heading2("Detailed Component Breakdown")
    
    doc.add_bullet("Tier 1 - Data Ingestion & Normalization:", 
                   "Accepts unstructured or tabular fee lists. Validates phone numbers to E.164 international format (+91XXXXXXXXXX), strips currency symbols, parses due dates into ISO-8601, and deduplicates records against active campaigns.")
    
    doc.add_bullet("Tier 2 - Campaign Dispatcher & Throttling Engine:", 
                   "Manages concurrent call limits to adhere to telecom carrier rate limits (e.g., 5-20 CPS - Calls Per Second). Implements regulatory time-window enforcement (e.g., calling strictly between 10:00 AM and 07:00 PM local time).")
    
    doc.add_bullet("Tier 3 - Telephony Gateway (SIP / WebSockets):", 
                   "Interfaces with Twilio, Plivo, or Exotel. Employs Answering Machine Detection (AMD) to identify human pickup vs. voicemail. When a human answers, it opens a bi-directional audio stream or TwiML Gather connection.")
    
    doc.add_bullet("Tier 4 - Real-Time Conversational AI Engine:", 
                   "Orchestrates Speech-to-Text (STT), conversational reasoning (LLM), and Text-to-Speech (TTS). Supports dynamic barge-in (caller interruption) so the parent can speak immediately without waiting for the bot to finish.")
    
    doc.add_bullet("Tier 5 - Extraction, Analytics & Reporting Engine:", 
                   "Parses call transcripts into structured JSON (payment status, tentative date, disputes). Updates the source Excel sheet with call outcomes and compiles a presentation-grade management PDF report.")

    # =========================================================================
    # PAGE 3: SYSTEM WORKING & STEP-BY-STEP OPERATION
    # =========================================================================
    doc.add_page()
    doc.add_heading1("3. Step-by-Step System Working & Operational Flow")
    doc.add_paragraph(
        "The operational lifecycle of a fee collection campaign executes across seven synchronized phases. "
        "The diagram and detailed walkthrough below specify exact triggers, data transformations, and state transitions."
    )
    
    doc.add_code_block([
        "  [1. Input Upload]    --> Admin uploads 'fees_defaulters_october.xlsx' or 'dues_ledger.pdf'.",
        "           |",
        "  [2. Validation]      --> Regex check phone numbers (+91), verify non-zero amounts, deduplicate.",
        "           |",
        "  [3. Batch Dispatch]  --> Push contacts to Redis Queue. Throttled dispatcher triggers calls via Twilio/Exotel.",
        "           |",
        "  [4. Pickup & AMD]    --> Answering Machine Detection: If voicemail -> drop reminder; If human -> connect AI.",
        "           |",
        "  [5. Spoken Dialogue] --> Bot greets caller, presents pending fee & due date, asks for payment commitment.",
        "           |",
        "  [6. AI Extraction]   --> LLM analyzes transcript: extracts outcome, tentative date, and dispute notes.",
        "           |",
        "  [7. Output Delivery] --> System writes 'call_disposition_report.xlsx' and builds executive summary PDF."
    ], title="Fig 2: Campaign Lifecycle Sequence")
    
    doc.add_heading2("Operational Stage Walkthrough")
    
    doc.add_bullet("Stage 1 - Ingestion & Schema Mapping: ", 
                   "The admin uploads an Excel file with columns (Student_Name, Parent_Name, Mobile_Number, Amount_Due, Due_Date, Institute_Name). The parser validates each row. Missing phone numbers or invalid values are isolated in an error log.")
    
    doc.add_bullet("Stage 2 - Call Scheduling & Throttling: ", 
                   "The dispatcher queries the queue and regulates dialing pace. If 1,000 parents are in the list, the system dials at a controlled concurrency (e.g., 10 parallel channels) to avoid telephony trunk saturation and ensure cloud server stability.")
    
    doc.add_bullet("Stage 3 - Call Pickup & Answering Machine Handling: ", 
                   "When the call rings and connects, the telephony carrier's AMD algorithm analyzes the initial audio packet: if an automated voicemail or IVR is detected, the bot leaves a concise payment notice and terminates. If human voice is detected, the conversational session begins.")
    
    doc.add_bullet("Stage 4 - Dialogue Execution & Dynamic Prompting: ", 
                   "The system dynamically injects row variables into the conversational prompt: 'Hello Mr. Sharma, this is an automated reminder from Apex Institute. We notice an overdue fee of Rs. 14,500 for Rahul Sharma, due on October 15th. Could you provide a tentative date when you will pay, or let us know if already paid?'")
    
    doc.add_bullet("Stage 5 - Response Capture & Classification: ", 
                   "The parent's spoken response is streamed to the Speech-to-Text model. A structured LLM parser categorizes the response into one of five formal disposition codes (ALREADY_PAID, PROMISE_TO_PAY, DISPUTED, EXTENSION_REQUEST, or WRONG_NUMBER).")
    
    doc.add_bullet("Stage 6 - Database Update & Disposition Tagging: ", 
                   "The system logs call metadata (Call SID, duration, timestamp, audio recording URL, full transcript, categorized outcome, and extracted tentative date) into a centralized audit ledger.")

    # =========================================================================
    # PAGE 4: CONVERSATIONAL LOGIC & STATE MACHINE
    # =========================================================================
    doc.add_page()
    doc.add_heading1("4. Spoken Dialogue Logic & State Machine")
    doc.add_paragraph(
        "The conversational agent operates as a deterministic finite state machine (FSM) with dynamic LLM reasoning "
        "at each node. This ensures the bot never hallucinate non-existent fee figures while maintaining polite, natural dialogue."
    )
    
    doc.add_code_block([
        "                           +-------------------------+",
        "                           |     STATE_INIT_CALL     |",
        "                           +-------------------------+",
        "                                        |",
        "                                        v",
        "                           +-------------------------+",
        "                           |  STATE_GREET_AND_INFORM |",
        "                           +-------------------------+",
        "                                        |",
        "                     +------------------+------------------+",
        "                     |                                     |",
        "                     v (Caller says: 'Already Paid')       v (Caller says: 'Will pay next week')",
        "         +-----------------------+             +-----------------------+",
        "         |   STATE_HANDLE_PAID   |             |   STATE_EXTRACT_DATE  |",
        "         +-----------------------+             +-----------------------+",
        "                     |                                     |",
        "                     v                                     v",
        "    +---------------------------------+   +---------------------------------+",
        "    | - Ask for transaction/UTR mode  |   | - Validate future date entity   |",
        "    | - Confirm accounting audit      |   | - Confirm exact date with caller|",
        "    +---------------------------------+   +---------------------------------+",
        "                     |                                     |",
        "                     +------------------+------------------+",
        "                                        |",
        "                                        v",
        "                           +-------------------------+",
        "                           |   STATE_CLOSING_THANKS  |",
        "                           +-------------------------+",
        "                                        |",
        "                                        v",
        "                           +-------------------------+",
        "                           |      STATE_HANGUP       |"
    ], title="Fig 3: Conversational Finite State Machine (FSM)")
    
    doc.add_heading2("Dialogue Branching Scenarios & Handling")
    
    doc.add_card("Branch 1: Parent Claims Already Paid", [
        "Spoken Input: 'I already paid Rs. 14,500 yesterday evening through Google Pay UPI.'",
        "Bot Response: 'Thank you for updating us! We will verify this transaction with our accounts desk. Please retain your UPI receipt. Have a great day ahead.'",
        "Extracted Output: { outcome: 'ALREADY_PAID', tentative_date: null, verification_required: true, payment_mode: 'UPI/GPay' }"
    ], r_border=0.12, g_border=0.55, b_border=0.24)
    
    doc.add_card("Branch 2: Parent Promises Future Date (Promise to Pay)", [
        "Spoken Input: 'My salary gets credited on the 7th of next month, so I will clear it by November 10th.'",
        "Bot Response: 'Understood. We have logged your tentative payment date as November 10th. An SMS confirmation has been sent. Thank you for your time!'",
        "Extracted Output: { outcome: 'PROMISE_TO_PAY', tentative_date: '2026-11-10', notes: 'Salary credited on 7th' }"
    ], r_border=0.15, g_border=0.35, b_border=0.60)
    
    doc.add_card("Branch 3: Fee Dispute / Financial Hardship / Installment Request", [
        "Spoken Input: 'The amount is wrong, Rahul received a 30% merit scholarship which is not deducted.'",
        "Bot Response: 'I apologize for the discrepancy. I have flagged your record for immediate manual review by our finance counselor. They will contact you shortly.'",
        "Extracted Output: { outcome: 'DISPUTED', tentative_date: null, manual_follow_up: true, dispute_reason: 'Scholarship deduction pending' }"
    ], r_border=0.78, g_border=0.45, b_border=0.05)

    # =========================================================================
    # PAGE 5: DATA SCHEMAS & EXTRACTION SPECIFICATION
    # =========================================================================
    doc.add_page()
    doc.add_heading1("5. Data Schemas & Extraction Specifications")
    doc.add_paragraph(
        "To guarantee high reliability and seamless integration with existing school management ERPs (e.g., Fedena, "
        "Salesforce Education Cloud, Tally, or custom portals), all inputs and outputs adhere to strict schemas."
    )
    
    doc.add_heading2("1. Input Dataset Schema (Excel / CSV / PDF Table)")
    in_headers = ["Field Name", "Type", "Required", "Sample Value", "Description"]
    in_rows = [
        ["student_id", "String", "Yes", "STU-2026-881", "Unique student enrollment identifier"],
        ["student_name", "String", "Yes", "Rahul Sharma", "Full name of the student"],
        ["parent_name", "String", "Yes", "Manoj Sharma", "Name of primary guardian / parent"],
        ["mobile_number", "String", "Yes", "+919876543210", "E.164 phone number to be called"],
        ["pending_amount", "Float", "Yes", "14500.00", "Total unpaid overdue fee balance in INR"],
        ["due_date", "String", "Yes", "2026-10-15", "Original fee deadline (ISO-8601 YYYY-MM-DD)"],
        ["institute_name", "String", "Yes", "Apex Academy", "Name of school, college, or institute"],
        ["course_class", "String", "Optional", "Grade 11 - PCM", "Class or academic batch"]
    ]
    doc.add_table(in_headers, in_rows, [95, 55, 60, 95, 194])
    
    doc.add_heading2("2. LLM Post-Call Structured Extraction Model (Pydantic)")
    doc.add_code_block([
        "from pydantic import BaseModel, Field",
        "from typing import Optional, Literal",
        "",
        "class CallDispositionExtraction(BaseModel):",
        "    outcome: Literal[",
        "        'ALREADY_PAID',       # Caller states fee is already paid",
        "        'PROMISE_TO_PAY',     # Caller provided a future tentative payment date",
        "        'EXTENSION_REQUEST',  # Caller asked for installment or financial extension",
        "        'DISPUTED',           # Caller disputes amount or fees policy",
        "        'WRONG_NUMBER',       # Recipient denies association with student",
        "        'UNREACHABLE'         # Call failed, unanswered, or voicemail",
        "    ] = Field(description='Primary call disposition outcome classification')",
        "    tentative_pay_date: Optional[str] = Field(",
        "        default=None, description='ISO date (YYYY-MM-DD) or explicit date mentioned by caller'",
        "    )",
        "    payment_reference_mode: Optional[str] = Field(",
        "        default=None, description='Payment channel if already paid (e.g., UPI, NetBanking, Cash)'",
        "    )",
        "    summary_notes: str = Field(description='Concise 1-sentence synopsis of caller statements')",
        "    manual_followup_flag: bool = Field(description='True if administrative intervention is required')"
    ], title="Pydantic Schema for Guaranteed Extraction")
    
    doc.add_heading2("3. Output Report Schema (Exported to Excel & PDF)")
    out_headers = ["Output Column", "Source", "Format", "Analytical Utility"]
    out_rows = [
        ["Call_Status", "Telephony Gateway", "COMPLETED / BUSY / NO_ANSWER", "Telephony success analysis"],
        ["Disposition_Code", "LLM Extraction", "PROMISE_TO_PAY / ALREADY_PAID", "Financial pipeline forecasting"],
        ["Tentative_Date", "LLM Extraction", "YYYY-MM-DD / N/A", "Cash flow scheduling & follow-ups"],
        ["Full_Transcript", "STT Engine", "Text String", "Legal compliance & quality audit"],
        ["Manual_Flag", "Rule Engine", "TRUE / FALSE", "Filters prioritized queue for counselors"]
    ]
    doc.add_table(out_headers, out_rows, [110, 110, 140, 139])

    # =========================================================================
    # PAGE 6: OPEN-SOURCE GITHUB REFERENCES & TECH STACK MATRIX
    # =========================================================================
    doc.add_page()
    doc.add_heading1("6. Open-Source GitHub References & Tech Stack Comparison")
    doc.add_paragraph(
        "Rather than inventing voice streaming protocols from scratch, production systems leverage proven "
        "open-source voice orchestration engines. The table below analyzes the top GitHub repositories for this use case."
    )
    
    ref_headers = ["Framework", "GitHub Repository", "Architecture Focus", "Recommended Application"]
    ref_rows = [
        ["Bolna", "bolna-ai/bolna", "Outbound Voice Campaigns", "Top Pick: Dedicated outbound dialer with built-in intent extraction."],
        ["Pipecat AI", "pipecat-ai/pipecat", "Real-Time Pipeline (WebSockets)", "Best for ultra-low latency (<500ms) and dynamic caller barge-in."],
        ["Twilio Agent", "twilio/twilio-agent-connect-python", "Twilio Native Connect", "Official Twilio scaffolding for OpenAI Realtime & ConversationRelay."],
        ["Deepgram Agent", "deepgram-devs/deepgram-voice-agent...", "Telephony + AMD", "Specialized in answering machine detection & voicemail drops."],
        ["Vocode", "vocodedev/vocode-python", "Conversational State Agent", "Python framework for phone calls, synthesis, and memory hooks."]
    ]
    doc.add_table(ref_headers, ref_rows, [80, 130, 130, 159])
    
    doc.add_heading2("Comparative Voice Stack Tradeoffs")
    
    doc.add_card("Architecture Option A: Twilio <Gather speech> (Fastest to Deploy & Lowest Cost)", [
        "Mechanism: Twilio handles STT natively via <Gather input='speech'> and posts transcript to a FastAPI webhook.",
        "Latency: 1.2s - 1.8s per turn (Turn-based half-duplex).",
        "Cost: ~$0.02 - $0.03 / min (Telephony) + $0.001 (LLM). Zero GPU infrastructure required.",
        "Verdict: Ideal for straightforward payment collection where the bot asks one question and records the answer."
    ], r_border=0.12, g_border=0.55, b_border=0.24)
    
    doc.add_card("Architecture Option B: Pipecat / Bolna WebSockets (Full Duplex with Barge-In)", [
        "Mechanism: Twilio Media Streams send 8kHz mulaw audio over WebSockets to Deepgram Nova-2 -> LLM -> Cartesia TTS.",
        "Latency: 350ms - 600ms (Real-time natural conversation).",
        "Cost: ~$0.05 - $0.09 / min (STT + LLM + TTS + Telephony).",
        "Verdict: Recommended if callers frequently interrupt, ask complex fee questions, or require fluid human-like speech."
    ], r_border=0.15, g_border=0.35, b_border=0.60)
    
    doc.add_card("Architecture Option C: OpenAI Realtime / Gemini Live Telephony Bridge", [
        "Mechanism: Direct speech-to-speech audio streaming through Twilio Media Streams.",
        "Latency: ~400ms end-to-end.",
        "Cost: ~$0.20 - $0.35 / min (Higher API pricing).",
        "Verdict: Excellent conversational nuance, but currently more expensive for high-volume automated debt campaigns."
    ], r_border=0.78, g_border=0.45, b_border=0.05)

    # =========================================================================
    # PAGE 7: PRODUCTION IMPLEMENTATION CODE SKELETON
    # =========================================================================
    doc.add_page()
    doc.add_heading1("7. Production Implementation Code Blueprint")
    doc.add_paragraph(
        "Below is the complete, modular Python implementation for the FastAPI telephony controller, LLM extraction engine, "
        "and automated Excel/PDF output generator."
    )
    
    doc.add_code_block([
        "# server.py - FastAPI Voice Telephony & Extraction Controller",
        "import os",
        "from fastapi import FastAPI, Form, Response",
        "from twilio.twiml.voice_response import VoiceResponse, Gather",
        "from openai import OpenAI",
        "from pydantic import BaseModel",
        "",
        "app = FastAPI(title='Fee Collection Voice Bot Server')",
        "client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))",
        "",
        "@app.post('/voice/start')",
        "async def voice_start(student: str, amount: str, due: str, inst: str):",
        "    vr = VoiceResponse()",
        "    prompt = (",
        "        f'Hello. This is an automated reminder from {inst}. '",
        "        f'Pending dues of rupees {amount} were due on {due} for student {student}. '",
        "        'Please specify when you will pay, or let us know if already paid.'",
        "    )",
        "    gather = Gather(",
        "        input='speech', speech_timeout='auto', timeout=7, language='en-IN',",
        "        action=f'/voice/process?student={student}&amount={amount}'",
        "    )",
        "    gather.say(prompt, voice='Polly.Aditi')  # Fluent Indian English",
        "    vr.append(gather)",
        "    vr.say('No response received. We will follow up later. Thank you.')",
        "    vr.hangup()",
        "    return Response(content=str(vr), media_type='application/xml')",
        "",
        "@app.post('/voice/process')",
        "async def voice_process(student: str, amount: str, SpeechResult: str = Form(default=''), CallSid: str = Form(...)):",
        "    vr = VoiceResponse()",
        "    if not SpeechResult:",
        "        vr.say('Thank you. Our team will contact you. Goodbye.')",
        "        vr.hangup()",
        "        return Response(content=str(vr), media_type='application/xml')",
        "",
        "    # LLM Structured Extraction",
        "    parsed = client.beta.chat.completions.parse(",
        "        model='gpt-4o-mini',",
        "        messages=[",
        "            {'role': 'system', 'content': 'Extract fee payment commitment status and tentative date.'},",
        "            {'role': 'user', 'content': f'Student: {student}, Due: {amount}. Caller said: {SpeechResult}'}",
        "        ],",
        "        response_format=CallDispositionExtraction",
        "    ).choices[0].message.parsed",
        "",
        "    # Dynamic Acknowledgment & Database Persistence",
        "    record_call_outcome(CallSid, student, amount, SpeechResult, parsed)",
        "    if parsed.outcome == 'ALREADY_PAID':",
        "        msg = 'Thank you for informing us. We will verify and update our records. Goodbye!'",
        "    elif parsed.outcome == 'PROMISE_TO_PAY':",
        "        msg = f'Thank you. We have noted that you will pay on {parsed.tentative_pay_date}. Goodbye!'",
        "    else:",
        "        msg = 'Thank you. We have recorded your notes for our accounts counselor. Goodbye!'",
        "",
        "    vr.say(msg, voice='Polly.Aditi')",
        "    vr.hangup()",
        "    return Response(content=str(vr), media_type='application/xml')"
    ], title="FastAPI Outbound Call Handler")

    # =========================================================================
    # PAGE 8: COMPLIANCE, REGULATIONS & PRODUCTION ROLLOUT
    # =========================================================================
    doc.add_page()
    doc.add_heading1("8. Legal Compliance, Telephony Regulations & Rollout Plan")
    doc.add_paragraph(
        "Automated voice dialers are strictly regulated worldwide. Deploying this system requires strict adherence "
        "to telecommunications guidelines in India (TRAI / DLT) and global standards (US TCPA / FCC)."
    )
    
    doc.add_heading2("1. Indian Telephony Regulatory Framework (TRAI & DLT)")
    doc.add_bullet("DLT Registration (Distributed Ledger Technology):", 
                   "Under TRAI regulations, any commercial or institutional entity making automated calls or SMS in India must register their Principal Entity (PE) ID and Telemarketer (TM) ID on telecom DLT portals (e.g., Jio, Airtel, Vodafone-Idea DLT).")
    doc.add_bullet("Transactional Voice Category:", 
                   "Fee reminder calls are classified as Service Implicit / Transactional. This allows dialing registered students even if their numbers are listed on the National Do Not Disturb (NDND / NDNC) registry, provided a pre-existing student relationship exists.")
    doc.add_bullet("Permitted Calling Hours:", 
                   "Automated dialers must only operate between 09:00 AM and 08:00 PM local time. The campaign dispatcher must enforce automatic queue suspension outside these hours.")
    doc.add_bullet("Consent & Audio Recording Disclosure:", 
                   "The call opening should incorporate a short disclosure: 'This call is an automated notice from [Institute] and is recorded for quality and verification purposes.'")
    
    doc.add_heading2("2. Multi-Phase Production Rollout Plan")
    rollout_headers = ["Phase", "Timeline", "Milestones", "Target Output"]
    rollout_rows = [
        ["Phase 1: Ingestion & Parser", "Week 1", "Build Excel & PDF parsers, validate E.164 phone data", "Clean tested JSON dataset"],
        ["Phase 2: Telephony Prototype", "Week 2", "Set up Twilio/Exotel account, configure FastAPI webhooks", "Test call to internal numbers"],
        ["Phase 3: Real-Time AI Agent", "Week 3", "Integrate Deepgram/Polly + GPT-4o-mini structured parser", "Sub-800ms intent recognition"],
        ["Phase 4: Output Engine", "Week 4", "Build Excel updater & executive PDF generator", "Closed-loop automated reports"],
        ["Phase 5: Pilot & Scale", "Week 5-6", "DLT approval, pilot with 200 real dues, full batch rollout", "Production scale (5k calls/day)"]
    ]
    doc.add_table(rollout_headers, rollout_rows, [110, 70, 200, 119])
    
    doc.add_card("Summary Recommendation for Implementation", [
        "Step 1: Use Exotel or Plivo if deploying primarily in India for native TRAI/DLT caller-ID compliance.",
        "Step 2: Start with the Twilio <Gather> / Bolna architecture for simplicity and rapid 2-week deployment.",
        "Step 3: Connect PostgreSQL to archive all call audio recordings, raw STT logs, and audit timestamps.",
        "Step 4: Schedule weekly automated PDF summary dispatches to the Chief Financial Officer (CFO) and Dean."
    ], r_border=0.08, g_border=0.22, b_border=0.45)
    
    # Save the document
    doc.build()

if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else "AUTOMATED_VOICE_AI_FEE_COLLECTION_SYSTEM_SPECIFICATION.pdf"
    create_specification_document(out_path)
