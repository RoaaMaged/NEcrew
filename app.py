import streamlit as st
from PIL import Image
import pandas as pd
import base64
import io
import requests
import re
from datetime import datetime
import cv2
import numpy as np
from passport_mrz_extractor import read_mrz
import easyocr

st.set_page_config(page_title="Passport OCR", layout="centered")
st.title("🛂 Universal Passport OCR with MRZ & Fallback")

reader = easyocr.Reader(['en'])

# Normalize and format date to DD-MMM-YY
def normalize_date(raw):
    if not raw:
        return ""
    raw = raw.replace("-", " ").replace("/", " ").upper()
    parts = raw.strip().split()
    try:
        if len(parts) == 3 and parts[1].isalpha():
            dt = datetime.strptime(" ".join(parts), "%d %b %Y")
            return dt.strftime("%d-%b-%y")
        compact = re.match(r"(\d{2})([A-Z]{3})(\d{2,4})", raw.replace(" ", ""))
        if compact:
            year = compact.group(3)
            if len(year) == 2:
                year = "19" + year if int(year) > 30 else "20" + year
            dt = datetime.strptime(compact.group(1) + " " + compact.group(2) + " " + year, "%d %b %Y")
            return dt.strftime("%d-%b-%y")
    except:
        return raw
    return raw

# OCR.Space API (primary OCR)
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

# Parse MRZ fields
def parse_mrz(image_path):
    try:
        mrz_data = read_mrz(image_path)
        return mrz_data
    except:
        return None

# EasyOCR fallback
def easyocr_text(img):
    img_np = np.array(img)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    result = reader.readtext(gray, detail=0)
    return "\n".join(result)

# Field extraction logic
def extract_passport_fields(img_path, pil_image, fallback_text=None):
    fields = {
        "Document Type": "P",
        "Passport Number": "",
        "Given Names": "",
        "Family Name": "",
        "Nationality": "",
        "Date of Birth": "",
        "Issuing Date": "",
        "Expiry Date": "",
        "Sex": "",
        "Country of Birth": "",
        "Issuing State": ""
    }

    mrz = parse_mrz(img_path)
    if mrz:
        fields["Passport Number"] = mrz.get("document_number", "")
        fields["Nationality"] = mrz.get("nationality", "")
        fields["Sex"] = "Male" if mrz.get("gender", "") == "M" else "Female"
        fields["Date of Birth"] = datetime.strptime(mrz["date_of_birth"], "%Y%m%d").strftime("%d-%b-%y")
        fields["Expiry Date"] = datetime.strptime(mrz["expiration_date"], "%Y%m%d").strftime("%d-%b-%y")

        names = mrz.get("surname", "") + " " + mrz.get("given_names", "")
        name_parts = names.strip().split(" ")
        if len(name_parts) >= 2:
            fields["Family Name"] = name_parts[0].title()
            fields["Given Names"] = " ".join(name_parts[1:]).title()
        elif len(name_parts) == 1:
            fields["Given Names"] = name_parts[0].title()

        fields["Country of Birth"] = fields["Nationality"]
        fields["Issuing State"] = fields["Nationality"]
        return fields

    # Fallback to EasyOCR/OCR.Space
    text = fallback_text or easyocr_text(pil_image)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    joined_text = " ".join(lines)

    # Passport No
    match = re.search(r"\b([A-Z]{1,2}\d{6,9})\b", joined_text)
    if match:
        fields["Passport Number"] = match.group()

    # Nationality
    match = re.search(r"\b(ITA|EGY|USA|IND|FRA|DEU|ESP|CAN|KSA|UAE|QAT)\b", joined_text)
    if match:
        fields["Nationality"] = match.group()

    # Dates
    all_dates = re.findall(r"\d{2}[-\s/]?[A-Z]{3,9}[-\s/]?\d{2,4}", joined_text)
    norm_dates = [normalize_date(d) for d in all_dates if normalize_date(d)]
    if norm_dates:
        fields["Date of Birth"] = norm_dates[0]
    if len(norm_dates) >= 2:
        fields["Issuing Date"] = norm_dates[1]
    if len(norm_dates) >= 3:
        fields["Expiry Date"] = norm_dates[-1]

    # Sex
    if re.search(r"\bSEX[:\s]*M\b", joined_text) or re.search(r"\bMALE\b", joined_text, re.IGNORECASE):
        fields["Sex"] = "Male"
    elif re.search(r"\bSEX[:\s]*F\b", joined_text) or re.search(r"\bFEMALE\b", joined_text, re.IGNORECASE):
        fields["Sex"] = "Female"

    # Country of Birth / Issuing State
    fields["Country of Birth"] = fields["Nationality"]
    fields["Issuing State"] = fields["Nationality"]

    # Names
    name_lines = []
    excluded_keywords = ["passport", "authority", "birth", "number", "expiry", "sex", "issued", "nationality"]
    for line in lines:
        if line.isupper() and line.replace(" ", "").isalpha() and not any(kw in line.lower() for kw in excluded_keywords):
            name_lines.append(line.title())

    if len(name_lines) >= 2:
        fields["Family Name"] = name_lines[0]
        fields["Given Names"] = name_lines[1]
    elif len(name_lines) == 1:
        fields["Given Names"] = name_lines[0]

    return fields

# Upload UI
uploaded_files = st.file_uploader("📸 Upload Passport Image(s)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
extracted_data = []

if uploaded_files:
    for img in uploaded_files:
        image = Image.open(img)
        st.image(image, caption=img.name, use_container_width=True)

        with st.spinner("🔍 Extracting text and parsing fields..."):
            # OCR.Space as fallback input
            ocr_space_text = extract_text_from_image(image)
            # Save image to disk for MRZ extractor (required)
            img_path = f"/tmp/{img.name}"
            image.save(img_path)

            fields = extract_passport_fields(img_path, image, fallback_text=ocr_space_text)
            extracted_data.append(fields)

        with st.expander(f"🧾 Extracted Passport Data - {img.name}", expanded=True):
            for key, value in fields.items():
                st.markdown(f"**{key}**: {value if value else '—'}")

# Download Excel
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
