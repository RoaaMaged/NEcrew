import streamlit as st
from PIL import Image
import pandas as pd
import base64
import io
import requests
import re

# --- CONFIG ---
st.set_page_config(page_title="Passport OCR", layout="centered")
st.title("🛂 Passport OCR Scanner")

# --- OCR Function ---
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

# --- Field Extraction ---
def extract_passport_fields(text):
    fields = {
        "Document Type": "P",
        "Passport Number": "",
        "Given Names": "",
        "Family Name": "",
        "Nationality": "",
        "Date of Birth": "",
        "Sex": "",
        "Expiry Date": ""
    }

    # Try to find each field by common patterns
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    lower_lines = [l.lower() for l in lines]

    for i, line in enumerate(lower_lines):
        if "passport" in line and "number" in line:
            for j in range(i, i+3):
                match = re.search(r"[A-Z]?\d{7,}", lines[j])
                if match:
                    fields["Passport Number"] = match.group().upper()
                    break

        if "name" in line or "given name" in line:
            if i+1 < len(lines):
                fields["Given Names"] = lines[i+1].title()

        if "surname" in line or "family name" in line:
            if i+1 < len(lines):
                fields["Family Name"] = lines[i+1].title()

        if "nationality" in line and i+1 < len(lines):
            nat = lines[i+1].lower()
            fields["Nationality"] = nat[:3].upper()

        if "sex" in line or "gender" in line:
            for j in range(i, i+2):
                if "male" in lower_lines[j]:
                    fields["Sex"] = "Male"
                elif "female" in lower_lines[j]:
                    fields["Sex"] = "Female"

        if "birth" in line:
            for j in range(i, i+3):
                dob = re.search(r"\d{2}/\d{2}/\d{4}", lines[j])
                if dob:
                    fields["Date of Birth"] = dob.group()
                    break

        if "expiry" in line or "expire" in line:
            for j in range(i, i+3):
                exp = re.search(r"\d{2}/\d{2}/\d{4}", lines[j])
                if exp:
                    fields["Expiry Date"] = exp.group()
                    break

    return fields

# --- File Upload ---
uploaded_files = st.file_uploader("Upload Passport Image(s)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    for img in uploaded_files:
        image = Image.open(img)
        st.image(image, caption=img.name, use_column_width=True)
        with st.spinner("Extracting data..."):
            text = extract_text_from_image(image)
            fields = extract_passport_fields(text)

        # --- Card-like Display ---
        with st.expander(f"🧾 Extracted Passport Data - {img.name}", expanded=True):
            for key, value in fields.items():
                st.markdown(f"**{key}**: {value if value else '—'}")

