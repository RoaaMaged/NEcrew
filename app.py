import streamlit as st
import requests
from PIL import Image
import pandas as pd
import io
import base64

st.title("📸 OCR Passport Field Extractor")

# ⬇️ OCR.Space API call
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

# ⬇️ Field extraction
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

    # Passport 3-letter codes
    mrz_country_codes = {
        "egypt": "EGY",
        "saudi arabia": "SAU",
        "united states": "USA",
        "united kingdom": "GBR",
        "india": "IND",
        "germany": "DEU",
        "france": "FRA",
        "qatar": "QAT",
        "kuwait": "KWT",
        "uae": "ARE",
        "jordan": "JOR",
        "lebanon": "LBN"
    }

    for line in text.split("\n"):
        line = line.strip().lower()

        if "type" in line and ":" in line:
            value = line.split(":")[-1].strip()
            fields["Document Type"] = "P" if "passport" in value else value
        elif "no" in line and ":" in line:
            fields["Document Number"] = line.split(":")[-1].strip()
        elif "nationality" in line and ":" in line:
            nat = line.split(":")[-1].strip().lower()
            fields["Nationality"] = mrz_country_codes.get(nat, nat[:3].upper())
        elif "surname" in line or "family" in line:
            fields["Family Name"] = " ".join(line.split()[1:])
        elif "given" in line:
            fields["Given Names"] = " ".join(line.split()[2:])
        elif "dob" in line or "date of birth" in line:
            fields["Date of Birth"] = line.split(":")[-1].strip()
        elif "sex" in line:
            fields["Sex"] = line.split(":")[-1].strip().capitalize()
        elif "country of birth" in line:
            fields["Country of Birth"] = line.split(":")[-1].strip().title()
        elif "issuing state" in line:
            fields["Issuing State"] = line.split(":")[-1].strip().title()
        elif "expiry" in line or "expire date" in line:
            fields["Document Expiry Date"] = line.split(":")[-1].strip()

    return fields

# ⬇️ UI
uploaded_images = st.file_uploader("Upload image(s)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_images:
    all_data = []

    for img in uploaded_images:
        image = Image.open(img)
        text = extract_text_from_image(image)
        fields = extract_fields(text)
        all_data.append(fields)

    df = pd.DataFrame(all_data)
    st.subheader("📋 Extracted Data")
    st.dataframe(df, use_container_width=True)
