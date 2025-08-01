import streamlit as st
import requests
from PIL import Image
import pandas as pd
import io
import base64
import re

st.title("📸 Passport/APIS OCR Extractor")

# --- OCR using OCR.Space ---
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

# --- Clean and extract fields ---
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

    # Clean lines
    raw_lines = [line.strip() for line in text.split("\n") if line.strip()]
    skip_keywords = ["at destination", "app response", "app explanation", "code", "etc", "explanation", "document place"]
    lines = [line for line in raw_lines if line.lower() not in skip_keywords]
    lines_lower = [line.lower() for line in lines]

    for i, line in enumerate(lines_lower):
        # Family and Given Names
        if line == "apis name" and i >= 2:
            fields["Family Name"] = lines[i - 2].strip().upper()
            fields["Given Names"] = lines[i - 1].strip().upper()

        # Nationality
        if line == "nationality" and i + 1 < len(lines):
            nat = lines[i + 1].strip().lower()
            fields["Nationality"] = mrz_country_codes.get(nat, nat[:3].upper())
            if fields["Nationality"] in mrz_country_codes.values():
                fields["Country of Birth"] = fields["Nationality"]

        # Issuing State
        if line == "passport" and i + 1 < len(lines):
            state = lines[i + 1].strip().lower()
            fields["Issuing State"] = mrz_country_codes.get(state, state[:3].upper())

        # Document Number
        if "document no" in line or "id number" in line:
            for j in range(i + 1, i + 4):
                if j < len(lines):
                    doc_no = lines[j].strip().upper()
                    if re.match(r"^[A-Z]?\d{7,}$", doc_no):
                        fields["Document Number"] = doc_no
                        break

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
            for j in range(i, i + 4):
                if j < len(lines):
                    dob = re.search(r"\d{2}/\d{2}/\d{4}", lines[j])
                    if dob:
                        fields["Date of Birth"] = dob.group()
                        break

        # Expiry Date
        if "expire" in line or "expiry" in line:
            for j in range(i, i + 4):
                if j < len(lines):
                    exp = re.search(r"\d{2}/\d{2}/\d{4}", lines[j])
                    if exp:
                        fields["Document Expiry Date"] = exp.group()
                        break

    return fields

# --- App Interface ---
uploaded_images = st.file_uploader("Upload APIS/passport image(s)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_images:
    all_results = []

    for img in uploaded_images:
        st.markdown(f"#### 📷 `{img.name}`")
        image = Image.open(img)
        text = extract_text_from_image(image)
        st.text_area("📝 Raw OCR Output", text, height=150)
        extracted = extract_fields(text)
        all_results.append(extracted)

    df = pd.DataFrame(all_results)
    st.markdown("### 📋 Extracted Data")
    st.dataframe(df, use_container_width=True)
