import streamlit as st
import os
import tempfile
import re
from datetime import datetime
from io import BytesIO

import google.generativeai as genai
from fpdf import FPDF
from PIL import Image
import fitz  # PyMuPDF

# ===============================
# GEMINI CONFIG
# ===============================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# ===============================
# PAGE CONFIG
# ===============================
st.set_page_config(
    page_title="WSP Graph Analyzer",
    page_icon="🚄",
    layout="wide"
)

# ===============================
# SIDEBAR
# ===============================
with st.sidebar:
    st.header("System Logic")
    st.info(
        "**Graph Rules:**\n\n"
        "🔴 Red Line: Reference Speed\n\n"
        "🎨 Colors: Axle Speeds\n\n"
        "📉 Fluctuation: Defect detected\n\n"
        "🟩 Green Pulse: Dump Valve Active\n\n"
        "🔵 Blue Pulse: Dump Valve Closure\n\n"
    )
    if os.getenv("GEMINI_API_KEY"):
        st.success("System Status: Online 🟢")
    else:
        st.error("System Status: Offline 🔴")

# ===============================
# HELPERS
# ===============================
def pdf_to_image(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.open(BytesIO(pix.tobytes("png")))
        doc.close()
        return img
    except Exception as e:
        st.error(f"PDF to image failed: {e}")
        return None


def extract_graph_period(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = doc[0].get_text()
        dates = re.findall(r'\d{2}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2}', text)
        doc.close()
        if len(dates) >= 2:
            return f"{dates[0]} to {dates[-1]}"
        return dates[0] if dates else "Not Available"
    except:
        return "Not Available"

# ===============================
# PDF CLASS
# ===============================
class EnhancedPDF(FPDF):
    def header(self):
        if self.page_no() > 2:
            self.set_font("Arial", "I", 8)
            self.set_text_color(120)
            self.cell(0, 10, f"WSP Graph Analyzer | Page {self.page_no()-2}", 0, 0, "R")
            self.ln(10)

    def add_heading(self, text, level=1):
        self.ln(3)
        if level == 1:
            self.set_font("Arial", "B", 14)
            self.set_fill_color(52, 152, 219)
            self.set_text_color(255)
            self.cell(0, 10, text, 0, 1, "L", True)
        else:
            self.set_font("Arial", "B", 12)
            self.set_text_color(0)
            self.cell(0, 8, text, 0, 1)
        self.ln(2)

    def add_paragraph(self, text):
        self.set_font("Arial", "", 10)
        self.multi_cell(0, 5, text.replace("**", ""))
        self.ln(2)

# ===============================
# REPORT GENERATION
# ===============================
def create_pdf_with_image(text, image_path, graph_period):
    pdf = EnhancedPDF()
    pdf.add_page()

    pdf.set_fill_color(70, 130, 180)
    pdf.rect(0, 0, pdf.w, pdf.h, "F")
    pdf.set_text_color(255)
    pdf.set_font("Arial", "B", 24)
    pdf.ln(80)
    pdf.cell(0, 15, "WSP GRAPH SUMMARY", 0, 1, "C")

    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"Generated: {datetime.now():%d-%m-%Y %H:%M:%S}", 0, 1, "C")
    pdf.cell(0, 8, f"Graph Timestamp: {graph_period}", 0, 1, "C")

    pdf.add_page()
    if image_path:
        pdf.image(image_path, x=10, w=pdf.w - 20)

    pdf.add_page()
    pdf.add_heading("Analysis Report")
    for line in text.split("\n"):
        if line.startswith("##"):
            pdf.add_heading(line.replace("##", "").strip(), level=2)
        else:
            pdf.add_paragraph(line)

    return pdf.output(dest="S").encode("latin-1")

# ===============================
# GEMINI ANALYSIS (FIXED)
# ===============================
def analyze_pdf(file_path):
    try:
        image = pdf_to_image(file_path)
        if image is None:
            return "Error: Could not extract image from PDF"

        model = genai.GenerativeModel("models/gemini-1.0-pro")

        response = model.generate_content(
            [
                PROMPT,
                image
            ]
        )

        return response.text if response and response.text else "Empty response"

    except Exception as e:
        return f"Error: {e}"

# ===============================
# UI
# ===============================
st.title("🚄 WSP Operational Graph Analyzer")
uploaded_file = st.file_uploader("Upload WSP Graph PDF", type=["pdf"])

# ===============================
# PROMPT (UNCHANGED)
# ===============================
PROMPT = """You are an expert railway braking systems analyst and WSP (Wheel Slide Protection) system engineer.

CRITICAL: You MUST follow the EXACT format specified below. Do not add, remove, or modify any sections.

====================
REQUIRED OUTPUT FORMAT
====================

You MUST generate your report in EXACTLY this format:

## Date of Analysis
[Current date in DD-MM-YYYY format]

## 1. Executive Summary
[Provide a brief 3-4 sentence overview of the operational period, key findings, and critical issues if any]

## 2. Speed and Axle Deviation Analysis

| Axle No. | Line Color | Observed Speed Condition | Phase of Anomaly | Conclusion |
|----------|------------|-------------------------|------------------|------------|
| Axle 1 | Green | [Description] | [Time period] | [Status] |
| Axle 2 | Yellow | [Description] | [Time period] | [Status] |
| Axle 3 | Blue | [Description] | [Time period] | [Status] |
| Axle 4 | Pink | [Description] | [Time period] | [Status] |

## 3. Wheel Slide Protection (WSP) System Response Analysis

| Axle No. | Dump Valve Activation (BV) | Dump Valve Closure (EV) | WSP System Status |
|----------|---------------------------|------------------------|-------------------|
| Axle 1 | [Description] | [Description] | [Status] |
| Axle 2 | [Description] | [Description] | [Status] |
| Axle 3 | [Description] | [Description] | [Status] |
| Axle 4 | [Description] | [Description] | [Status] |

## 4. Diagnosis
[Provide detailed technical diagnosis based on observations. Include specific timestamps and measurements where visible]

## 5. Recommendations
[List specific, actionable maintenance recommendations based on the diagnosis]

====================
TECHNICAL REFERENCE (Use this to fill the tables)
====================

LINE COLOR DEFINITIONS:
- Red line (#FE0000): Reference Speed (train reference speed)
- Green line (#00FF01): Axle 1 Speed
- Yellow line (#FFFF00): Axle 2 Speed
- Blue line (#0000FE): Axle 3 Speed
- Pink line (#FF00FE): Axle 4 Speed

DUMP VALVE COLOR CODING:
- #9A99FF: Dump valve activation for Axle 1
- #6599FF: Dump valve activation for Axle 2
- #6665FE: Dump valve activation for Axle 3
- #3401CC: Dump valve activation for Axle 4

ANALYSIS RULES:

For "Observed Speed Condition":
- "Tracking reference speed smoothly" if axle follows red line
- "Fluctuating with deviations" if axle shows variations
- "Severe drops below reference" if axle drops significantly
- "Complete wheel lock" if speed drops to zero

For "Phase of Anomaly":
- Specify time range (e.g., "16.00s - 30.75s")
- Use "None" if no anomaly detected
- Use "Multiple periods" if anomalies occur at different times

For "Conclusion":
- "Normal Operation" if tracking reference smoothly
- "Affected - Minor" for small deviations with quick recovery
- "Affected - Moderate" for repeated fluctuations
- "Severely Affected" for prolonged wheel lock or major deviations

For "Dump Valve Activation (BV)":
- "Activated immediately" if BV responds when needed
- "Multiple rapid activations" for frequent cycling
- "Sustained activation" for prolonged pressure dump
- "No activation detected" if no BV signal when needed

For "Dump Valve Closure (EV)":
- "Proper closure after recovery" if EV follows BV correctly
- "Rapid cycling" for quick open-close patterns
- "Delayed closure" if EV timing is off
- "No closure signal" if missing

For "WSP System Status":
- "Functioning Correctly" if BV activates when needed and EV follows properly
- "Partially Effective" if system responds but with delays
- "Malfunction Suspected" if no BV activation despite wheel slip
- "Requires Maintenance" if system shows irregular behavior

====================
CRITICAL INSTRUCTIONS
====================

1. Use ONLY the section headings provided above
2. Fill ALL four rows in BOTH tables (one row per axle)
3. Keep table format EXACTLY as shown with pipe separators
4. Base your analysis ONLY on what you observe in the graph
5. Do not add extra sections or subsections
6. Use professional railway engineering terminology
7. Be concise but technically accurate
8. If you cannot determine something, state "Cannot determine from graph" rather than guessing

        """

# ===============================
# EXECUTION
# ===============================
if uploaded_file and st.button("Generate Diagnostic Report"):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    with st.spinner("Analyzing with Gemini Flash…"):
        graph_period = extract_graph_period(tmp_path)
        image = pdf_to_image(tmp_path)

        img_path = None
        if image:
            img_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
            image.save(img_path)

        report = analyze_pdf(tmp_path)

        st.subheader("📋 Analysis Result")
        st.markdown(report)

        if image:
            st.image(image, caption="WSP Graph")

        st.download_button(
            "📄 Download PDF Report",
            create_pdf_with_image(report, img_path, graph_period),
            file_name="WSP_Report.pdf",
            mime="application/pdf"
        )

    os.unlink(tmp_path)
