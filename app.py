import streamlit as st
import easyocr
import cv2
import string
import json
from dateutil import parser
import tempfile
import os

# Load EasyOCR reader
reader = easyocr.Reader(['en'], gpu=False)

# Load country codes
try:
    with open("country_codes.json") as f:
        country_codes = json.load(f)
except FileNotFoundError:
    st.error("❌ 'country_codes.json' not found.")
    st.stop()

# Utility functions
def parse_date(s):
    try:
        date = parser.parse(s, yearfirst=True).date()
        return date.strftime('%d/%m/%Y')
    except Exception:
        return ""

def clean(s):
    return ''.join(c for c in s if c.isalnum()).upper()

def get_country_name(code):
    for c in country_codes:
        if c['alpha-3'] == code:
            return c['name'].upper()
    return code

def get_sex(code):
    if code.upper() in ['M', 'F']:
        return code.upper()
    elif code == '0':
        return 'M'
    return 'F'

# MRZ Extraction logic
def extract_mrz_from_easyocr(image_path):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    height = gray.shape[0]

    # Crop bottom 20% to find MRZ
    cropped = gray[int(height * 0.8):, :]
    results = reader.readtext(cropped, detail=0)
    mrz_lines = [line.replace(" ", "").upper() for line in results if len(line) >= 30]

    if len(mrz_lines) >= 2:
        return mrz_lines[-2], mrz_lines[-1]
    return None, None

def extract_passport_data_easyocr(image_path):
    a, b = extract_mrz_from_easyocr(image_path)
    if not a or not b:
        return None

    a = a + '<' * (44 - len(a)) if len(a) < 44 else a
    b = b + '<' * (44 - len(b)) if len(b) < 44 else b

    surname_names = a[5:44].split('<<', 1)
    surname, names = surname_names if len(surname_names) == 2 else (surname_names[0], "")

    return {
        "Name": names.replace('<', ' ').strip().upper(),
        "Surname": surname.replace('<', ' ').strip().upper(),
        "Sex": get_sex(clean(b[20])),
        "Date of Birth": parse_date(b[13:19]),
        "Nationality": get_country_name(clean(b[10:13])),
        "Passport Type": clean(a[0:2]),
        "Passport Number": clean(b[0:9]),
        "Issuing Country": get_country_name(clean(a[2:5])),
        "Expiration Date": parse_date(b[21:27]),
        "Personal Number": clean(b[28:42]),
    }

# Streamlit UI
st.set_page_config(page_title="Passport OCR (No Tesseract)", layout="centered")
st.title("🛂 Passport OCR App (EasyOCR-only)")

uploaded_file = st.file_uploader("Upload a passport image", type=["jpg", "jpeg", "png"])

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        tmp.write(uploaded_file.read())
        temp_path = tmp.name

    st.image(temp_path, caption="Uploaded Passport", use_column_width=True)
    st.write("🔍 Extracti
