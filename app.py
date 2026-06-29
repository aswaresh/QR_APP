import os
import pandas as pd
import qrcode
from flask import Flask, render_template, request, send_file
from PIL import Image, ImageDraw, ImageFont
import zipfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "static/generated"   # ✅ for preview

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# -----------------------------
# Convert mm → pixels (300 DPI)
# -----------------------------
def mm_to_px(mm):
    return int((mm * 300) / 25.4)

# -----------------------------
# QR + label
# -----------------------------
def create_qr_with_text(data, width, height, filepath):

    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((width, height))

    text_height = int(height * 0.25)
    final_img = Image.new("RGB", (width, height + text_height), "white")
    final_img.paste(img, (0, 0))

    draw = ImageDraw.Draw(final_img)
    font_size = int(width * 0.15)

    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()

    text_width = draw.textlength(data, font=font)
    text_x = (width - text_width) // 2

    draw.text((text_x, height + int(text_height * 0.2)), data, fill="black", font=font)

    final_img.save(filepath)

# -----------------------------
# Home
# -----------------------------
@app.route("/")
def index():
    return render_template("upload.html")

# -----------------------------
# Generate + Preview
# -----------------------------
@app.route("/generate", methods=["POST"])
def generate():

    mode = request.form.get("mode", "excel")
    output_type = request.form["output_type"]
    layout = request.form["layout"]

    width_mm = float(request.form["width"])
    height_mm = float(request.form["height"])

    width = mm_to_px(width_mm)
    height = mm_to_px(height_mm)

    # ✅ Validation
    if width < 100 or height < 100:
        return render_template("upload.html", error="⚠ Size too small (Minimum 20mm)")

    if width > 2000 or height > 2000:
        return render_template("upload.html", error="⚠ Size too large (Maximum 200mm)")

    # ✅ CLEAR OLD FILES
    for f in os.listdir(OUTPUT_FOLDER):
        os.remove(os.path.join(OUTPUT_FOLDER, f))

    # ---------------- DATA ----------------
    if mode == "excel":
        file = request.files.get("file")

        if not file or file.filename == "":
            return render_template("upload.html", error="⚠ Please upload Excel file")

        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)

        df = pd.read_excel(filepath)
        ids = df.iloc[:, 0].dropna().astype(str).unique()

    else:
        manual_id = request.form.get("manual_id", "").strip()

        if not manual_id:
            return render_template("upload.html", error="⚠ Enter Equipment ID")

        ids = [manual_id]

    # ---------------- Generate Images ----------------
    image_files = []

    for eid in ids:
        filename = os.path.join(OUTPUT_FOLDER, f"{eid}.png")
        create_qr_with_text(eid, width, height, filename)
        image_files.append(filename)

    return render_template(
        "preview.html",
        images=[os.path.basename(f) for f in image_files],
        output_type=output_type,
        layout=layout
    )

# -----------------------------
# Download
# -----------------------------
@app.route("/download", methods=["POST"])
def download():

    output_type = request.form["output_type"]
    layout = request.form["layout"]

    IMAGE_FOLDER = "static/generated"
    OUTPUT_FOLDER_LOCAL = "output"

    os.makedirs(OUTPUT_FOLDER_LOCAL, exist_ok=True)

    image_files = [
        os.path.join(IMAGE_FOLDER, f)
        for f in os.listdir(IMAGE_FOLDER)
        if f.endswith(".png")
    ]

    # ---------------- ZIP ----------------
    if output_type == "zip":
        zip_path = os.path.join(OUTPUT_FOLDER_LOCAL, "qr_codes.zip")

        with zipfile.ZipFile(zip_path, "w") as zipf:
            for img in image_files:
                zipf.write(img, os.path.basename(img))

        return send_file(zip_path, as_attachment=True)

    # ---------------- PDF ----------------
    elif output_type == "pdf":

        pdf_path = os.path.join(OUTPUT_FOLDER_LOCAL, "qr_codes.pdf")
        c = canvas.Canvas(pdf_path, pagesize=A4)

        page_width, page_height = A4

        margin = 20
        text_height = 30

        qr_size = 300   # display size in PDF

        cell_width = qr_size + margin
        cell_height = qr_size + text_height + margin

        cols = int(page_width // cell_width)
        rows = int(page_height // cell_height)

        x_start = (page_width - (cols * cell_width)) / 2
        y_start = page_height - margin

        count = 0

        for img in image_files:

            col = count % cols
            row = (count // cols) % rows

            x = x_start + col * cell_width
            y = y_start - (row + 1) * cell_height

            c.drawImage(img, x, y,
                        width=qr_size,
                        height=qr_size + text_height)

            count += 1

            if count % (cols * rows) == 0:
                c.showPage()

        c.save()

        return send_file(pdf_path, as_attachment=True)

    return "Invalid option"

from flask import send_from_directory

@app.route("/download-template")
def download_template():
    return send_from_directory(
        directory=".",
        path="template.xlsx",
        as_attachment=True
    )


# -----------------------------
# Run
# -----------------------------
if __name__ == "__main__":
    app.run()
