import streamlit as st
import requests
from PIL import Image
import pandas as pd
import io
import base64
import re

st.title("📸 Passport/APIS Field Extractor")

# --- OCR via OCR.Space ---
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

# --- Field Extractor for APIS Layout ---
def extract_fields(text):
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
        # Given Names
        if "apis name" in line and i > 0:
            fields["Given Names"] = lines[i - 1].strip().upper()

        # Family Name
        if "apis surname" in line and i + 1 < len(lines):
            fields["Family Name"] = lines[i + 1].strip().upper()

        # Document Number
        if "document no" in line or "id number" in line:
            for j in range(i + 1, i + 4):
                if j < len(lines):
                    doc = lines[j].strip()
                    if len(doc) >= 7 and any(c.isdigit() for c in doc):
                        fields["Document Number"] = doc.upper()
                        break

        # Nationality
        if "nationality" in line and i + 1 < len(lines):
            nat = lines[i + 1].strip().lower()
            fields["Nationality"] = mrz_country_codes.get(nat, nat[:3].upper())
            fields["Country of Birth"] = fields["Nationality"]

        # Issuing State
        if "at origin" in line and i + 1 < len(lines):
            origin = lines[i + 1].strip().lower()
            fields["Issuing State"] = mrz_country_codes.get(origin, origin[:3].upper())

        # Sex
        if "gender" in line or "sex" in line:
            for j in range(i, i + 3):
                if j < len(lines):
                    if "male" in lines[j].lower():
                        fields["Sex"] = "Male"
                        break
                    elif "female" in lines[j].lower():
                        fields["Sex"] = "Female"
                        break

        # Date of Birth
        if "birth" in line:
            for j in range(i, i + 3):
                if j < len(lines):
                    match = re.search(r'\d{2}/\d{2}/\d{4}', lines[j])
                    if match:
                        fields["Date of Birth"] = match.group()
                        break

        # Expiry Date
        if "expire" in line or "expiry" in line:
            for j in range(i, i + 3):
                if j < len(lines):
                    match = re.search(r'\d{2}/\d{2}/\d{4}', lines[j])
                    if match:
                        fields["Document Expiry Date"] = match.group()
                        break

    # If nothing extracted, fallback
    if all(v == "" for v in fields.values()):
        return {"OCR Text": text.strip()}

    return fields

# --- Upload and Display ---
uploaded_images = st.file_uploader("Upload APIS/passport images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_images:
    results = []

    for img in uploaded_images:
        st.markdown(f"#### 📷 Processing `{img.name}`")
        image = Image.open(img)
        text = extract_text_from_image(image)
        st.text_area("📝 Raw OCR Output", text, height=120)
        fields = extract_fields(text)
        results.append(fields)
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
