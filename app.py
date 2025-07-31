import streamlit as st
import requests
from PIL import Image
import pandas as pd
import io
import base64
import re

st.title("📸 OCR Passport/APIS Extractor")

# --- OCR API Call ---
def extract_text_from_image(image_file):
    api_key = st.secrets["OCR_SPACE_API_KEY"]
    buffered = io.BytesIO()
    image_file.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    response = requests.post(
        "https://api.ocr.space/parse/image",
        data={
            "base64Image": "data:image/jpeg;base64," + img_str,
            "language": "eng",
            "apikey": api_key
        },
    )
    result = response.json()
    if result.get("IsErroredOnProcessing"):
        return ""
    return result["ParsedResults"][0]["ParsedText"]

# --- Extract Fields from OCR Text ---
def extract_fields(text):
    fields = {
        "Document Type": "",
        "Nationality": "",
        "Document Number": "",
        "Document Expiry Date": "",
        "Issuing State": "",
        "Family Name": "",
        "Given Names": "",
        "Date of Birth": "",
        "Sex": "",
        "Country of Birth": ""
    }

    mrz_country_codes = {
        "egypt": "EGY", "saudi arabia": "SAU", "united states": "USA",
        "united kingdom": "GBR", "india": "IND", "germany": "DEU",
        "france": "FRA", "qatar": "QAT", "kuwait": "KWT", "uae": "ARE",
        "jordan": "JOR", "lebanon": "LBN", "sa": "SAU"
    }

    lines = [line.strip() for line in text.lower().split("\n") if line.strip()]

    for idx, line in enumerate(lines):
        # Document Type
        if "passport" in line:
            fields["Document Type"] = "P"

        # Nationality
        if "nationality" in line or "country" in line or "origin" in line:
            for country in mrz_country_codes:
                if country in line:
                    fields["Nationality"] = mrz_country_codes[country]
                    break

        # Document Number
        if "document no" in line or "document number" in line or "id number" in line:
            match = re.search(r'\b[a-z]?\d{6,}', line)
            if match:
                fields["Document Number"] = match.group().upper()

        # Family Name / Surname
        if "surname" in line or "family" in line:
            parts = lines[idx + 1].split() if idx + 1 < len(lines) else []
            fields["Family Name"] = parts[0].upper() if parts else ""

        # Given Names (based on APIS NAME or Name line)
        if "name" in line and "apis" in line:
            parts = lines[idx + 1].split() if idx + 1 < len(lines) else []
            fields["Given Names"] = " ".join(parts).upper()

        # Sex
        if "gender" in line or "sex" in line:
            if "male" in line:
                fields["Sex"] = "Male"
            elif "female" in line:
                fields["Sex"] = "Female"
            else:
                next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
                if "male" in next_line:
                    fields["Sex"] = "Male"
                elif "female" in next_line:
                    fields["Sex"] = "Female"

        # Date of Birth
        if "date of birth" in line or "dob" in line:
            match = re.search(r'\d{2}/\d{2}/\d{4}', line)
            if match:
                fields["Date of Birth"] = match.group()

        # Document Expiry Date
        if "expire" in line or "expiry" in line:
            match = re.search(r'\d{2}/\d{2}/\d{4}', line)
            if match:
                fields["Document Expiry Date"] = match.group()

        # Issuing State
        if "document place" in line or "at origin" in line:
            for country in mrz_country_codes:
                if country in line:
                    fields["Issuing State"] = mrz_country_codes[country]
                    break

        # Country of Birth fallback
        if not fields["Country of Birth"]:
            fields["Country of Birth"] = fields["Nationality"]

    # If nothing matched, fallback
    if all(v == "" for v in fields.values()):
        return {"OCR Text": text.strip()}
    return fields

# --- Upload and Extract ---
uploaded_images = st.file_uploader("Upload image(s)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_images:
    results = []

    for img in uploaded_images:
        st.markdown(f"#### 📷 Processing `{img.name}`")
        image = Image.open(img)
        text = extract_text_from_image(image)
        st.text_area("📝 Raw OCR Output", text, height=150)
        fields = extract_fields(text)
        results.append(fields)
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
