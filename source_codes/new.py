from pdfengine import PDFLayoutEngine
engine = PDFLayoutEngine()

engine.add_cover_page(graph_period)
# engine.add_graph_page(img_temp_path)

engine.add_section_title("Summary")
engine.add_paragraph(parsed_report["summary"])

engine.add_section_title("Axle Analysis")
engine.add_table(parsed_report["axle_analysis_table"])

engine.add_section_title("WSP Status")
engine.add_paragraph(parsed_report["wsp_status"])

engine.add_section_title("Recommendations")
for rec in parsed_report["recommendations"]:
    engine.add_paragraph(f"- {rec}")

pdf_bytes = engine.export()
