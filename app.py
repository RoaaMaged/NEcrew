import streamlit as st
import requests
from PIL import Image
import pandas as pd
import io
import base64
import re

st.title("📸 Passport/APIS OCR Extractor")

# --- OCR ---
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

# --- Field Extraction for Your Layout ---
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

    lines = [line.strip() fo]()
