import streamlit as st
from PIL import Image
import pandas as pd
import io
import base64
import requests
import re

st.set_page_config(page_title="Passport OCR", layout="centered")
st.title("🛂 Passport / APIS OCR Scanner")

# --- OCR function using OCR.Space API ---
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

# --- Field extractor ---
def extract_passport_fields(text):
    fields = {
        "Document Type": "P",
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

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    lines_lower = [line.lower() for line in lines]

    for i, line in enumerate(lines_lower):
        if "apis name" in line and i >= 2:
            fields["Family Name"] = lines[i - 2].upper()
            fields["Given Names"] = lines[i - 1].upper()

        if "nationality" in line and i + 1 < len(lines):
            nat = lines[i + 1].strip().lower()
            fields["Nationality"] = mrz_country_codes.get(nat, nat[:3].upper())
            fields["Country of Birth"] = fields["Nationality"]

        if "passport" in line and i + 1 < len(lines):
            state = lines[i + 1].strip().lower()
            fields["Issuing State"] = mrz_country_codes.get(state, state[:3].upper())

        if "document no" in line or "id number" in line:
            for j in range(i + 1, i + 3):
                if j < len(lines):
                    val = lines[j].strip()
                    if re.match(r"[A-Z]?\d{7,}", val):
                        fields["Document Number"] = val.upper()
                        break

        if "birth" in line:
            for j in range(i, i + 3):
                match = re.search(r"\d{2}/\d{2}/\d{4}", lines[j])
                if match:
                    fields["Date of Birth"] = match.group()
                    break

        if "expire" in line:
            for j in range(i, i + 3):
                match = re.search(r"\d{2}/\d{2}/\d{4}", lines[j])
                if match:
                    fields["Document Expiry Date"] = match.group()
                    break

        if "gender" in line or "sex" in line:
            for j in range(i, i + 3):
                if "male" in lines[j].lower():
                    fields["Sex"] = "Male"
                    break
                elif "female" in lines[j].lower():
                    fields["Sex"] = "Female"
                    break

    return fields

# --- Upload and Process ---
uploaded_files = st.file_uploader("Upload Passport/APIS Image(s)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    extracted_data = []

    for img in uploaded_files:
        image = Image.open(img)
        st.image(image, caption=img.name, use_column_width=True)
        with st.spinner(f"Processing {img.name}..."):
            text = extract_text_from_image(image)
            fields = extract_passport_fields(text)
            extracted_data.append(fields)

    df = pd.DataFrame(extracted_data)
    st.markdown("### 📋 Extracted Fields")
    st.dataframe(df, use_container_width=True)
