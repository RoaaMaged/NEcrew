import streamlit as st
from PIL import Image
import pandas as pd
import base64
import io
import requests
import re
import numpy as np
import easyocr
import cv2
from passporteye import read_mrz
from passporteye.util.ocr import ocr

# ----- Patch passporteye OCR to use EasyOCR -----
def easyocr_ocr(image, extra_cmdline_params=None):
    reader = easyocr.Reader(['en'], gpu=False)
    result = reader.readtext(np.array(image), detail=0)
    return "\n".join(result)

ocr.__code__ = easyocr_ocr.__code__

# ----- Page Config -----
st.set_page_config(page_title="Passport OCR", layout="centered")
st.title("🛂 Universal Passport OCR")

# ----- OCR using OCR.Space -----
def extract_text_from_image(image_file):
    api_key = st.secrets["OCR_SPACE_API_KEY"]
    buffered = io.BytesIO()
    image_file.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    response = requests.post(
        "https://api.ocr.space/parse/image",
        data={
            "base64Image": f"data:image/jpeg;base64,{img_str}",
            "language": "eng",
            "apikey": api_key
        },
    )
    result = response.json()
    if result.get("IsErroredOnProcessing"):
        return ""
    return result["ParsedResults"][0]["ParsedText"]

# ----- Normalize Date Format -----
def normalize_date(raw):
    if not raw:
        return ""
    match = re.search(r"(\d{2})[-\s]?([A-Z]{3})[-\s]?(\d{2,4})", raw.upper())
    if match:
        day, mon, year = match.groups()
        if len(year) == 4:
            year = year[-2:]  # Only last 2 digits
        return f"{int(day):02d}-{mon.capitalize()}-{year}"
    return raw

# ----- Extract MRZ -----
def extract_mrz_data(image_file):
    mrz = read_mrz(image_file)
    if mrz:
        mrz_data = mrz.to_dict()
        return {
            "Passport Number": mrz_data.get("number", ""),
            "Nationality": mrz_data.get("nationality", ""),
            "Date of Birth": normalize_date(mrz_data.get("date_of_birth", "")),
            "Sex": mrz_data.get("sex", "").capitalize(),
            "Expiry Date": normalize_date(mrz_data.get("expiration_date", "")),
            "Issuing State": mrz_data.get("issuing_country", "")
        }
    return {}

# ----- Main Field Extraction -----
def extract_passport_fields(text, mrz_fields):
    fields = {
        "Document Type": "P",
        "Passport Number": mrz_fields.get("Passport Number", ""),
        "Given Names": "",
        "Family Name": "",
        "Nationality": mrz_fields.get("Nationality", ""),
        "Date of Birth": mrz_fields.get("Date of Birth", ""),
        "Issuing Date": "",
        "Expiry Date": mrz_fields.get("Expiry Date", ""),
        "Sex": mrz_fields.get("Sex", ""),
        "Country of Birth": mrz_fields.get("Issuing State", ""),
        "Issuing State": mrz_fields.get("Issuing State", "")
    }

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    joined_text = " ".join(lines)

    # Issuing Date
    issue_date_match = re.search(r"Issue(?:d)?\s*[:\-]?\s*(\d{2}[\s/-]?[A-Z]{3}[\s/-]?\d{2,4})", joined_text, re.IGNORECASE)
    if issue_date_match:
        fields["Issuing Date"] = normalize_date(issue_date_match.group(1))

    # Name Detection
    excluded_keywords = [
        "passport", "passaporto", "authority", "repubblica", "document",
        "birth", "expiry", "number", "code", "nationality", "sex", "issued"
    ]
    name_lines = []
    for line in lines:
        if (
            line.isupper()
            and line.replace(" ", "").isalpha()
            and not any(kw in line.lower() for kw in excluded_keywords)
            and len(line.split()) >= 1
            and not re.match(r"^[A-Z]{2,4}$", line.strip())
        ):
            name_lines.append(line.title())

    if len(name_lines) >= 2:
        fields["Family Name"] = name_lines[0]
        fields["Given Names"] = name_lines[1]
    elif len(name_lines) == 1:
        fields["Given Names"] = name_lines[0]

    # Fallback Country of Birth
    if not fields["Country of Birth"]:
        for line in lines:
            if "birth" in line.lower():
                fields["Country of Birth"] = fields["Nationality"]

    return fields

# ----- UI: Upload Section -----
uploaded_files = st.file_uploader("📸 Upload Passport Image(s)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
extracted_data = []

if uploaded_files:
    for img in uploaded_files:
        image = Image.open(img)
        st.image(image, caption=img.name, use_container_width=True)

        with st.spinner("🔍 Extracting text..."):
            text = extract_text_from_image(image)
            st.text_area("📝 Raw OCR Output", text, height=150)

            mrz_fields = extract_mrz_data(img)
            fields = extract_passport_fields(text, mrz_fields)
            extracted_data.append(fields)

        with st.expander(f"🧾 Extracted Passport Data - {img.name}", expanded=True):
            for key, value in fields.items():
                st.markdown(f"**{key}**: {value if value else '—'}")

# ----- Download as Excel -----
if extracted_data:
    df = pd.DataFrame(extracted_data)
    towrite = io.BytesIO()
    df.to_excel(towrite, index=False, sheet_name="Passport Data")
    towrite.seek(0)
    st.download_button(
        label="📥 Download Excel",
        data=towrite,
        file_name="passport_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
