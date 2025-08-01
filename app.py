import streamlit as st
from PIL import Image
import pandas as pd
import base64
import io
import requests
import re
import cv2
import pytesseract
import easyocr
from passporteye import read_mrz
import numpy as np

st.set_page_config(page_title="Passport OCR", layout="centered")
st.title("🛂 Universal Passport OCR")

# Helper: Normalize dates like 18-Apr-73
def normalize_date(raw):
    if not raw:
        return ""
    match = re.search(r"(\d{2})[^\dA-Z]*([A-Z]{3})[^\dA-Z]*(\d{2,4})", raw.upper())
    if not match:
        return ""
    day, mon, year = match.groups()
    if len(year) == 4:
        year = year[-2:]
    return f"{day}-{mon.title()}-{year}"

# OCR using OCR.Space
def ocr_space_text(image_file):
    try:
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
    except Exception:
        return ""

# OCR fallback: Tesseract → EasyOCR
def fallback_ocr(img):
    try:
        text = pytesseract.image_to_string(img)
        if len(text.strip()) > 10:
            return text
    except:
        pass
    try:
        reader = easyocr.Reader(['en'])
        result = reader.readtext(np.array(img), detail=0)
        return "\n".join(result)
    except:
        return ""

# Extract MRZ
def extract_mrz_data(image_file):
    mrz = read_mrz(image_file)
    if not mrz:
        return {}
    data = mrz.to_dict()
    return {
        "Passport Number": data.get("number", ""),
        "Nationality": data.get("nationality", ""),
        "Date of Birth": normalize_date(data.get("date_of_birth", "")),
        "Sex": "Male" if data.get("sex") == "M" else "Female" if data.get("sex") == "F" else "",
        "Expiry Date": normalize_date(data.get("expiration_date", "")),
        "Issuing Date": "",
        "Issuing State": data.get("country", ""),
        "Country of Birth": data.get("country", "")
    }

# Extract names from OCR text
def extract_names_from_text(text):
    excluded_keywords = [
        "passport", "passaporto", "authority", "repubblica", "document",
        "birth", "expiry", "number", "code", "nationality", "sex", "issued"
    ]
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    name_lines = [
        line.title() for line in lines
        if line.isupper()
        and line.replace(" ", "").isalpha()
        and not any(kw in line.lower() for kw in excluded_keywords)
        and len(line.split()) >= 1
        and not re.match(r"^[A-Z]{2,4}$", line.strip())
    ]
    family, given = "", ""
    if len(name_lines) >= 2:
        family, given = name_lines[0], name_lines[1]
    elif len(name_lines) == 1:
        given = name_lines[0]
    return family, given

# Upload UI
uploaded_files = st.file_uploader("📸 Upload Passport Image(s)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
extracted_data = []

if uploaded_files:
    for img in uploaded_files:
        image = Image.open(img)
        st.image(image, caption=img.name, use_container_width=True)

        with st.spinner("🔍 Extracting text..."):
            text = ocr_space_text(image)
            if not text:
                text = fallback_ocr(image)
            st.text_area("📝 Raw OCR Output", text, height=150)

            mrz_fields = extract_mrz_data(img)

            family_name, given_names = extract_names_from_text(text)

            fields = {
                "Document Type": "P",
                "Passport Number": mrz_fields.get("Passport Number", ""),
                "Given Names": given_names,
                "Family Name": family_name,
                "Nationality": mrz_fields.get("Nationality", ""),
                "Date of Birth": mrz_fields.get("Date of Birth", ""),
                "Issuing Date": mrz_fields.get("Issuing Date", ""),
                "Expiry Date": mrz_fields.get("Expiry Date", ""),
                "Sex": mrz_fields.get("Sex", ""),
                "Country of Birth": mrz_fields.get("Country of Birth", ""),
                "Issuing State": mrz_fields.get("Issuing State", "")
            }

            # Align Country of Birth = Issuing State
            if not fields["Country of Birth"]:
                fields["Country of Birth"] = fields["Issuing State"]

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
