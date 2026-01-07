# #this library for desktop app
# import tkinter as tk
# from tkinter import filedialog

import streamlit as st
from google import genai
import os
# import google.generativeai as genai
from google.genai import types
import tempfile

from fpdf import FPDF
from PIL import Image
import fitz  # PyMuPDF for PDF to image conversion
from datetime import datetime
import re
from io import BytesIO
# genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
# --- Page Configuration ---
st.set_page_config(
    page_title="WSP Graph Analyzer",
    page_icon="🚄",
    layout="wide"
)


# this function is for desktop app
# def save_pdf_dialog(pdf_bytes):
#     root = tk.Tk()
#     root.withdraw()  # hide empty window

#     file_path = filedialog.asksaveasfilename(
#         defaultextension=".pdf",
#         filetypes=[("PDF files", "*.pdf")],
#         title="Save Report As"
#     )

#     if file_path:
#         with open(file_path, "wb") as f:
#             f.write(pdf_bytes)
#         return file_path

#     return None


# --- Backend Configuration ---
if "GEMINI_API_KEY" in st.secrets:
    API_KEY = st.secrets["GEMINI_API_KEY"]
elif os.getenv("GEMINI_API_KEY"):
    API_KEY = os.getenv("GEMINI_API_KEY")
else:
    API_KEY = "YOUR_API_KEY_HERE"

# --- Sidebar ---
with st.sidebar:
    st.header("System Logic")
    st.info(
        "**Graph Rules:**\n\n"
        "🔴 **Red Line:** Reference Speed\n\n"
        "🎨 **Colors:** Axle Speeds\n\n"
        "📉 **Fluctuation:** Defect detected\n\n"
        "🟩 **Green Pulse:** Dump Valve Active\n\n"
        "🔵 **Blue Pulse:** Dump Valve Closure\n\n"
    )
    if API_KEY and API_KEY != "YOUR_API_KEY_HERE":
        st.success("System Status: Online 🟢")
    else:
        st.error("System Status: Offline 🔴")

# --- Helper: Convert PDF to Image ---
def pdf_to_image(pdf_path):
    """Convert first page of PDF to image"""
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        img = Image.open(BytesIO(img_data))
        doc.close()
        return img
    except Exception as e:
        st.error(f"Error converting PDF to image: {e}")
        return None

# --- Helper: Extract Graph Period from PDF ---
def extract_graph_period(pdf_path):
    """Extract graph period from PDF using text extraction"""
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        text = page.get_text()
        
        # Look for date patterns like "18.01.25 07:10:24"
        date_pattern = r'\d{2}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2}'
        dates = re.findall(date_pattern, text)
        
        if len(dates) >= 2:
            return f"{dates[0]} to {dates[-1]}"
        elif len(dates) == 1:
            return dates[0]
        
        doc.close()
        return "Not Available"
    except:
        return "Not Available"

# --- Enhanced PDF Class with Table Support ---
class EnhancedPDF(FPDF):
    def header(self):
        if self.page_no() > 2:  # Skip header for cover and image pages
            self.set_font('Arial', 'I', 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, f'WSP Graph Analyzer - Page {self.page_no() - 2}', 0, 0, 'R')
            self.ln(10)
    
    def add_heading(self, text, level=1):
        """Add formatted heading"""
        self.ln(3)
        if level == 1:
            self.set_font('Arial', 'B', 14)
            self.set_fill_color(52, 152, 219)
            self.set_text_color(255, 255, 255)
            safe_text = text.encode('ascii', 'ignore').decode('ascii')
            self.cell(0, 10, safe_text, 0, 1, 'L', True)
        elif level == 2:
            self.set_font('Arial', 'B', 12)
            self.set_text_color(0, 0, 0)
            safe_text = text.encode('ascii', 'ignore').decode('ascii')
            self.cell(0, 8, safe_text, 0, 1, 'L')
        self.set_text_color(0, 0, 0)
        self.ln(2)
    
    def add_paragraph(self, text):
        """Add paragraph text"""
        self.set_font('Arial', '', 10)
        # Clean special characters
        text = text.replace('\u2019', "'").replace('\u2018', "'")
        text = text.replace('\u201c', '"').replace('\u201d', '"')
        text = text.replace('\u2013', '-').replace('\u2014', '-')
        text = text.replace('**', '')
        safe_text = text.encode('ascii', 'ignore').decode('ascii')
        self.multi_cell(0, 5, safe_text)
        self.ln(2)
    
    def add_table(self, headers, rows):
        """Add formatted table with dynamic sizing"""
        # Calculate optimal column widths based on content
        num_cols = len(headers)
        available_width = self.w - 20  # Total width minus margins
        
        # Analyze content to determine optimal widths
        max_content_lengths = []
        for col_idx in range(num_cols):
            max_len = len(str(headers[col_idx]))
            for row in rows:
                if col_idx < len(row):
                    max_len = max(max_len, len(str(row[col_idx])))
            max_content_lengths.append(max_len)
        
        # Calculate proportional widths
        total_content = sum(max_content_lengths)
        if total_content > 0:
            col_widths = [(length / total_content) * available_width for length in max_content_lengths]
            # Ensure minimum width of 20mm per column
            col_widths = [max(20, w) for w in col_widths]
            # Adjust if total exceeds available width
            total_width = sum(col_widths)
            if total_width > available_width:
                scale = available_width / total_width
                col_widths = [w * scale for w in col_widths]
        else:
            # Equal distribution if no content
            col_widths = [available_width / num_cols] * num_cols
        
        # Check if table fits on page
        if self.get_y() + 20 > self.h - 30:
            self.add_page()
        
        # Draw header
        self.set_font('Arial', 'B', 9)
        self.set_fill_color(52, 152, 219)
        self.set_text_color(255, 255, 255)
        
        # Calculate header height
        header_height = 10
        max_header_lines = 1
        for i, header in enumerate(headers):
            clean_header = str(header).replace('**', '').strip()
            chars_per_line = int(col_widths[i] * 2.2)
            lines_needed = max(1, (len(clean_header) // chars_per_line) + 1)
            max_header_lines = max(max_header_lines, lines_needed)
        header_height = max(10, max_header_lines * 5)
        
        # Draw header cells
        x_start = self.get_x()
        y_start = self.get_y()
        
        for i, header in enumerate(headers):
            clean_header = str(header).replace('**', '').strip()
            clean_header = clean_header.encode('ascii', 'ignore').decode('ascii')
            
            # Draw border
            self.set_xy(x_start + sum(col_widths[:i]), y_start)
            self.cell(col_widths[i], header_height, '', 1, 0, 'C', True)
            
            # Add text
            self.set_xy(x_start + sum(col_widths[:i]) + 1, y_start + 1)
            self.multi_cell(col_widths[i] - 2, 4, clean_header, 0, 'C')
        
        self.set_xy(x_start, y_start + header_height)
        
        # Draw rows
        self.set_font('Arial', '', 8)
        self.set_text_color(0, 0, 0)
        
        for row_idx, row in enumerate(rows):
            # Clean and prepare all cells
            cleaned_cells = []
            cell_line_counts = []
            
            for i, cell in enumerate(row):
                # Clean text
                clean_cell = str(cell).replace('**', '').strip()
                clean_cell = clean_cell.replace('\u2019', "'").replace('\u2018', "'")
                clean_cell = clean_cell.replace('\u201c', '"').replace('\u201d', '"')
                clean_cell = clean_cell.replace('\u2013', '-').replace('\u2014', '-')
                safe_cell = clean_cell.encode('ascii', 'ignore').decode('ascii')
                cleaned_cells.append(safe_cell)
                
                # Calculate lines needed using word wrapping
                chars_per_line = int(col_widths[i] * 2.2)
                words = safe_cell.split()
                lines = []
                current_line = ""
                
                for word in words:
                    test_line = current_line + " " + word if current_line else word
                    if len(test_line) <= chars_per_line:
                        current_line = test_line
                    else:
                        if current_line:
                            lines.append(current_line)
                        current_line = word
                
                if current_line:
                    lines.append(current_line)
                
                cell_line_counts.append(max(1, len(lines)))
            
            # Calculate row height
            max_lines = max(cell_line_counts) if cell_line_counts else 1
            row_height = max(10, max_lines * 4 + 2)  # 4mm per line + 2mm padding
            
            # Check if row fits on page
            if self.get_y() + row_height > self.h - 20:
                self.add_page()
                self.set_xy(x_start, self.get_y())
            
            # Set alternating colors
            if row_idx % 2 == 0:
                self.set_fill_color(255, 255, 255)
            else:
                self.set_fill_color(245, 245, 245)
            
            # Get current position
            x_pos = self.get_x()
            y_pos = self.get_y()
            
            # Draw all cell borders first
            for i in range(len(cleaned_cells)):
                self.set_xy(x_pos + sum(col_widths[:i]), y_pos)
                self.cell(col_widths[i], row_height, '', 1, 0, 'L', True)
            
            # Add text to each cell
            for i, cell_text in enumerate(cleaned_cells):
                cell_x = x_pos + sum(col_widths[:i]) + 1
                cell_y = y_pos + 1
                
                self.set_xy(cell_x, cell_y)
                
                # Use multi_cell for automatic wrapping
                # Calculate available height
                available_height = row_height - 2
                
                # Add text with wrapping
                self.multi_cell(col_widths[i] - 2, 3.5, cell_text, 0, 'L')
            
            # Move to next row
            self.set_xy(x_pos, y_pos + row_height)
        
        self.ln(5)

# --- Helper: Create PDF with Table Parsing ---
def create_pdf_with_image(text_content, image_path, graph_period):
    """Create PDF report with proper markdown parsing"""
    pdf = EnhancedPDF()
    
    # ===== COVER PAGE =====
    pdf.add_page()
    generated_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    
    # Full-page background color
    pdf.set_fill_color(70, 130, 180)
    pdf.rect(0, 0, pdf.w, pdf.h, style='F')
    pdf.set_text_color(255, 255, 255)
    
    # Move to center
    pdf.set_y(pdf.h / 2 - 30)
    
    # Title
    pdf.set_font('Arial', 'B', 24)
    pdf.ln(20)
    pdf.cell(0, 15, 'WSP GRAPH SUMMARY', 0, 1, 'C')
    pdf.ln(10)
    
    # Metadata
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f'Generated Time : {generated_time}', 0, 1, 'C')
    pdf.cell(0, 8, f'Graph Timestamp : {graph_period}', 0, 1, 'C')
    pdf.ln(30)
    
    # Company branding
    pdf.set_font("Arial", 'I', size=9)
    pdf.cell(0, 5, "This report is generated by Premade Innovations Pvt. Ltd.", 0, 1, 'C')
    
    # ===== GRAPH IMAGE PAGE =====
    pdf.add_page()
    pdf.set_text_color(0, 0, 0)
    
    if image_path and os.path.exists(image_path):
        try:
            img = Image.open(image_path)
            img_width, img_height = img.size
            page_width = pdf.w - 20
            scale_factor = page_width / img_width
            scaled_height_px = img_height * scale_factor
            scaled_height_mm = (scaled_height_px / 96) * 25.4
            
            current_y = pdf.get_y()
            max_height = pdf.h - current_y - 30
            
            if scaled_height_mm > max_height:
                scale_factor_height = max_height / scaled_height_mm
                final_width = page_width * scale_factor_height
                pdf.image(image_path, x=10 + (page_width - final_width) / 2, y=current_y, w=final_width)
            else:
                pdf.image(image_path, x=10, y=current_y, w=page_width)
        except Exception as e:
            pdf.set_font('Arial', '', 10)
            pdf.cell(0, 10, f'[Image could not be embedded: {e}]', 0, 1)
    
    # ===== ANALYSIS CONTENT PAGE =====
    pdf.add_page()
    pdf.add_heading('Analysis Report', level=1)
    
    # Add current date and graph timestamp
    current_date = datetime.now().strftime("%d-%m-%Y")
    
    # Add Date of Analysis section
    pdf.add_heading('Date of Analysis', level=2)
    pdf.add_paragraph(current_date)
    pdf.add_heading('Graph Timestamp', level=2)
    pdf.add_paragraph(graph_period)
    
    # Parse content
    lines = text_content.split('\n')
    table_data = []
    in_table = False
    skip_date_section = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Skip markdown separator lines
        if line.startswith('|') and all(c in '|:-' for c in line.replace(' ', '')):
            continue
        
        # Detect headings (## 1. or ## Date of Analysis, etc.)
        if line.startswith('##'):
            # Close any open table
            if in_table and len(table_data) > 1:
                pdf.add_table(table_data[0], table_data[1:])
                in_table = False
                table_data = []
            
            heading_text = line.replace('##', '').strip()
            
            # Skip Date of Analysis section as we already added it
            if 'Date of Analysis' in heading_text or heading_text.startswith('Date'):
                skip_date_section = True
                continue
            
            skip_date_section = False
            pdf.add_heading(heading_text, level=2)
        
        # Detect tables
        elif '|' in line and not skip_date_section:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if parts:
                if not in_table:
                    in_table = True
                    table_data = [parts]
                else:
                    table_data.append(parts)
        
        # Regular text
        else:
            if not skip_date_section:
                if in_table and len(table_data) > 1:
                    pdf.add_table(table_data[0], table_data[1:])
                    in_table = False
                    table_data = []
                
                if not line.startswith('---') and line:
                    pdf.add_paragraph(line)
    
    # Add remaining table
    if in_table and len(table_data) > 1:
        pdf.add_table(table_data[0], table_data[1:])
    
    return pdf.output(dest='S').encode('latin-1')

# --- Helper: Create Text File ---
def create_text_with_image_info(text_content, image_path, graph_period):
    """Create text file with image reference"""
    generated_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    
    output = "=" * 70 + "\n"
    output += "WSP GRAPH SUMMARY\n"
    output += "=" * 70 + "\n\n"
    output += f"Generated Time : {generated_time}\n"
    output += f"Graph Timestamp : {graph_period}\n\n"
    
    if image_path and os.path.exists(image_path):
        output += "[GRAPH IMAGE INCLUDED - See PDF version for visual reference]\n\n"
    
    output += "-" * 70 + "\n"
    output += "ANALYSIS REPORT\n"
    output += "-" * 70 + "\n\n"
    output += text_content
    output += "\n\n" + "=" * 70 + "\n"
    output += "This report is generated by Premade Innovations Pvt. Ltd.\n"
    output += "=" * 70 + "\n"
    
    return output

# --- Main Interface ---
st.title("🚄 WSP Operational Graph Analyzer")
uploaded_file = st.file_uploader("Choose a PDF Graph file", type=["pdf"])

# --- Analysis Logic ---
def analyze_pdf(file_path, key):
    if not key or key == "YOUR_API_KEY_HERE":
        return "Error: Invalid API Key."

    try:
        client = genai.Client(api_key=key)
        
        with open(file_path, "rb") as f:
            file_content = f.read()

        prompt = """
You are an expert railway braking systems analyst and WSP (Wheel Slide Protection) system engineer.

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

        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=file_content, mime_type="application/pdf")
                    ]
                )
            ]
        )
        
        if response and hasattr(response, 'text'):
            return response.text if response.text else "Error: Empty response from AI"
        else:
            return "Error: Invalid response format from AI"
            
    except Exception as e:
        return f"An error occurred: {str(e)}"

# --- Execution ---
if uploaded_file and st.button("Generate Diagnostic Report"):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name

    with st.spinner("Analyzing with Gemini Flash Latest..."):
        # Extract graph period
        graph_period = extract_graph_period(tmp_path)
        
        # Convert PDF to image
        graph_image = pdf_to_image(tmp_path)
        
        # Save image temporarily
        img_temp_path = None
        if graph_image:
            img_temp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
            graph_image.save(img_temp_path)
        
        # Generate analysis report
        report = analyze_pdf(tmp_path, API_KEY)
        
        if report is None or "Error" in str(report):
            st.error(report if report else "Analysis failed - No response received")
        else:
            # Display metadata
            col_meta1, col_meta2 = st.columns(2)
            with col_meta1:
                st.info(f"**Generated Time:** {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
            with col_meta2:
                st.info(f"**Graph Timestamp:** {graph_period}")
            
            st.divider()
            
            # Display Graph Image
            if graph_image:
                st.subheader("📊 Uploaded Graph")
                st.image(graph_image, caption="WSP Operational Graph", width='stretch')
                st.divider()
            
            # Display Report
            st.subheader("📋 Analysis Result")
            st.markdown(report)
            st.divider()
            
            # Download Options
            st.subheader("📥 Download Options")
            col1, col2, col3 = st.columns(3)
            
            # Download Graph Image
            if graph_image and img_temp_path:
                with col1:
                    with open(img_temp_path, "rb") as img_file:
                        st.download_button(
                            label="🖼️ Download Graph (.png)",
                            data=img_file.read(),
                            file_name="WSP_Graph.png",
                            mime="image/png",
                        )
            
            # Download Text Report
            with col2:
                text_content = create_text_with_image_info(report, img_temp_path, graph_period)
                st.download_button(
                    label="📄 Download Report (.txt)",
                    data=text_content,
                    file_name="WSP_Analysis_Report.txt",
                    mime="text/plain",
                )
            
            # Download PDF
            with col3:
                try:
                    pdf_data = create_pdf_with_image(report, img_temp_path, graph_period)
                    st.download_button(
                        label="📕 Download Full Report (.pdf)",
                        data=pdf_data,
                        file_name="WSP_Analysis_Report.pdf",
                        mime="application/pdf",
                        
                    )
                except Exception as e:
                    st.warning(f"PDF generation failed: {e}")
        
        # Cleanup
        if img_temp_path and os.path.exists(img_temp_path):
            os.unlink(img_temp_path)
    
    os.unlink(tmp_path)