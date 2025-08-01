import streamlit as st
from PIL import Image
import pandas as pd
import base64
import io
import requests
import re

# --- Config ---
st.set_page_config(page_title="Passport OCR", layout="centered")
st.title("🛂 Universal Passport OCR")

# --- OCR from ocr.space ---
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

# --- Smart Passport Field Extraction ---
def extract_passport_fields(text):
    fields = {
        "Document Type": "P",
        "Passport Number": "",
        "Given Names": "",
        "Family Name": "",
        "Nationality": "",
        "Date of Birth": "",
        "Sex": "",
        "Expiry Date": "",
        "Country of Birth": "",
        "Issuing State": ""
    }

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    text_lower = [l.lower() for l in lines]

    for i, line in enumerate(text_lower):
        original = lines[i]

        # Passport number
        if any(x in line for x in ["passport no", "passport number", "n. passport"]):
            match = re.search(r"[A-Z]?[0-9]{7,10}", original)
            if match:
                fields["Passport Number"] = match.group().upper()

        # Nationality
        if "nationality" in line:
            if i+1 < len(lines):
                nat = lines[i+1].strip()
                fields["Nationality"] = nat[:3].upper()

        # Issuing state / country
        if "repubblica" in line or "state" in line:
            match = re.search(r"\b[A-Z]{3}\b", original)
            if match:
                fields["Issuing State"] = match.group().upper()

        # Names
        if "surname" in line or "family name" in line:
            if i+1 < len(lines):
                fields["Family Name"] = lines[i+1].strip().title()

        if "given name" in line or "name" in line:
            if i+1 < len(lines):
                fields["Given Names"] = lines[i+1].strip().title()

        # Date of Birth
        if "birth" in line:
            for j in range(i, i+3):
                dob = re.search(r"\d{2}[/\s\-]?[A-Za-z]{3}[/\s\-]?\d{4}", lines[j])
                if dob:
                    fields["Date of Birth"] = dob.group().replace(" ", "/").replace("-", "/").upper()
                    break

        # Expiry
        if "expiry" in line or "expire" in line or "expiration" in line:
            for j in range(i, i+3):
                exp = re.search(r"\d{2}[/\s\-]?[A-Za-z]{3}[/\s\-]?\d{4}", lines[j])
                if exp:
                    fields["Expiry Date"] = exp.group().replace(" ", "/").replace("-", "/").upper()
                    break

        # Sex
        if "sex" in line or "gender" in line:
            for j in range(i, i+2):
                if "male" in lines[j].lower():
                    fields["Sex"] = "Male"
                elif "female" in lines[j].lower():
                    fields["Sex"] = "Female"
                elif "m" in lines[j].lower():
                    fields["Sex"] = "Male"
                elif "f" in lines[j].lower():
                    fields["Sex"] = "Female"

        # Country of Birth
        if "place of birth" in line or "birthplace" in line or "country of birth" in line:
            if i+1 < len(lines):
                fields["Country of Birth"] = lines[i+1].strip().title()

    return fields

# --- Upload & Process ---
uploaded_files = st.file_uploader("📸 Upload Passport Image(s)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    for img in uploaded_files:
        image = Image.open(img)
        st.image(image, caption=img.name, use_container_width=True)

        with st.spinner("🔍 Extracting text..."):
            text = extract_text_from_image(image)
            st.text_area("📝 Raw OCR Output", text, height=150)
            fields = extract_passport_fields(text)

        # Display clean result
        with st.expander(f"🧾 Extracted Passport Data - {img.name}", expanded=True):
            for key, value in fields.items():
                st.markdown(f"**{key}**: {value if value else '—'}")
