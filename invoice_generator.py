from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime
import os

def generate_invoice_pdf(customer_data, items):
    invoice_id = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    filename = f"{invoice_id}.pdf"
    output_dir = "invoices"
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, filename)

    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4

    # Header
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, height - 50, "Invoice")

    c.setFont("Helvetica", 12)
    c.drawString(50, height - 80, f"Invoice ID: {invoice_id}")
    c.drawString(50, height - 100, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Customer Info
    c.drawString(50, height - 140, f"Customer Name: {customer_data.get('Name')}")
    c.drawString(50, height - 160, f"Phone: {customer_data.get('Phone', 'N/A')}")
    c.drawString(50, height - 180, f"Email: {customer_data.get('Email', 'N/A')}")

    # Table headers
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 220, "Item")
    c.drawString(250, height - 220, "Qty")
    c.drawString(320, height - 220, "Rate")
    c.drawString(400, height - 220, "Total")

    # Items
    y = height - 240
    c.setFont("Helvetica", 12)
    grand_total = 0
    for item in items:
        c.drawString(50, y, item["name"])
        c.drawString(250, y, str(item["qty"]))
        c.drawString(320, y, f"₹{item['rate']:.2f}")
        c.drawString(400, y, f"₹{item['total']:.2f}")
        grand_total += item["total"]
        y -= 20

    # Grand total
    c.setFont("Helvetica-Bold", 12)
    c.drawString(320, y - 20, "Grand Total:")
    c.drawString(400, y - 20, f"₹{grand_total:.2f}")

    c.save()
    return pdf_path