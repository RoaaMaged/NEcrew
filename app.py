import streamlit as st
from PIL import Image
import pandas as pd
import base64
import io
import requests
import re

st.set_page_config(page_title="Passport OCR", layout="centered")
st.title("🛂 Universal Passport OCR")

# OCR using OCR.Space
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

# Clean and normalize date strings
def normalize_date(raw):
    if not raw:
        return ""
    # Fix things like "12 FEB/ FEB 2001" → "12 FEB 2001"
    fixed = re.sub(r"/\s*([A-Z]{3})", r" \1", raw.upper())
    fixed = re.sub(r"\s+", " ", fixed.strip())
    return fixed.replace("-", "/")

# Passport Field Extraction Logic
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
    joined_text = " ".join(lines)

    # Passport Number
    passport_no = re.search(r"\b([A-Z]{1,2}\d{6,9})\b", joined_text)
    if passport_no:
        fields["Passport Number"] = passport_no.group()

    # Nationality (ISO codes)
    nationality = re.search(r"\b(ITA|EGY|USA|IND|FRA|DEU|ESP|CAN|KSA|UAE|QAT)\b", joined_text)
    if nationality:
        fields["Nationality"] = nationality.group()

    # Dates
    all_dates = re.findall(r"\d{2}[\s/-]?[A-Z]{3}[\s/-]?[A-Z]{3}?[\s/-]?\d{4}", joined_text)
    normalized_dates = [normalize_date(d) for d in all_dates]
    if normalized_dates:
        fields["Date of Birth"] = normalized_dates[0]
    if len(normalized_dates) > 1:
        fields["Expiry Date"] = normalized_dates[-1]

    # Sex
    if re.search(r"\bmale\b", joined_text, re.IGNORECASE):
        fields["Sex"] = "Male"
    elif re.search(r"\bfemale\b", joined_text, re.IGNORECASE):
        fields["Sex"] = "Female"
    elif re.search(r"\bM\b", joined_text):
        fields["Sex"] = "Male"
    elif re.search(r"\bF\b", joined_text):
        fields["Sex"] = "Female"

    # Country of Birth — use after Date of Birth if present
    for line in lines:
        if "maracaibo" in line.lower() or "birth" in line.lower():
            fields["Country of Birth"] = line.title()
            break

    # Issuing State — from known keywords
    for line in lines:
        if any(kw in line.lower() for kw in ["repubblica", "authority", "ministry", "state"]):
            code_match = re.search(r"\b[A-Z]{3}\b", line)
            if code_match:
                fields["Issuing State"] = code_match.group()

    # Family / Given Name detection (heuristic)
    name_lines = []
    for line in lines:
        if line.isupper() and not any(kw in line.lower() for kw in ["passport", "repubblica", "authority", "birth", "expiry", "document"]):
            words = line.split()
            if 1 <= len(words) <= 4 and all(len(w) > 2 for w in words):
                name_lines.append(line.title())

    if len(name_lines) >= 2:
        fields["Family Name"] = name_lines[0]
        fields["Given Names"] = name_lines[1]
    elif len(name_lines) == 1:
        fields["Given Names"] = name_lines[0]

    return fields

# File uploader and display
uploaded_files = st.file_uploader("📸 Upload Passport Image(s)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
extracted_data = []

if uploaded_files:
    for img in uploaded_files:
        image = Image.open(img)
        st.image(image, caption=img.name, use_container_width=True)

        with st.spinner("🔍 Extracting text..."):
            text = extract_text_from_image(image)
            st.text_area("📝 Raw OCR Output", text, height=150)
            fields = extract_passport_fields(text)
            extracted_data.append(fields)

        with st.expander(f"🧾 Extracted Passport Data - {img.name}", expanded=True):
            for key, value in fields.items():
                st.markdown(f"**{key}**: {value if value else '—'}")

# Excel download
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
