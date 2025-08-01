import streamlit as st
from PIL import Image
import pandas as pd
import base64
import io
import requests
import re
from datetime import datetime

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

# Normalize and format date to DD-MMM-YY
def normalize_date(raw):
    if not raw:
        return ""
    raw = raw.replace("-", " ").replace("/", " ").upper()
    parts = raw.strip().split()
    try:
        if len(parts) == 3 and parts[1].isalpha():
            dt = datetime.strptime(" ".join(parts), "%d %b %Y")
            return dt.strftime("%d-%b-%y")
        compact = re.match(r"(\d{2})([A-Z]{3})(\d{4})", raw.replace(" ", ""))
        if compact:
            dt = datetime.strptime(compact.group(1) + " " + compact.group(2) + " " + compact.group(3), "%d %b %Y")
            return dt.strftime("%d-%b-%y")
    except:
        return raw
    return raw

# Extract passport fields
def extract_passport_fields(text):
    fields = {
        "Document Type": "P",
        "Passport Number": "",
        "Given Names": "",
        "Family Name": "",
        "Nationality": "",
        "Date of Birth": "",
        "Issuing Date": "",
        "Expiry Date": "",
        "Sex": "",
        "Country of Birth": "",
        "Issuing State": ""
    }

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    joined_text = " ".join(lines)

    # Passport Number
    passport_no = re.search(r"\b([A-Z]{1,2}\d{6,9})\b", joined_text)
    if passport_no:
        fields["Passport Number"] = passport_no.group()

    # Nationality
    nationality = re.search(r"\b(ITA|EGY|USA|IND|FRA|DEU|ESP|CAN|KSA|UAE|QAT)\b", joined_text)
    if nationality:
        fields["Nationality"] = nationality.group()

    # Extract all potential dates
    all_dates = re.findall(r"\d{2}[\s/-]?[A-Z]{3}[\s/-]?\d{4}", joined_text)
    normalized_dates = [normalize_date(d) for d in all_dates]

    if normalized_dates:
        fields["Date of Birth"] = normalized_dates[0]
    if len(normalized_dates) >= 2:
        fields["Issuing Date"] = normalized_dates[1]
    if len(normalized_dates) >= 3:
        fields["Expiry Date"] = normalized_dates[-1]

    # Sex
    if re.search(r"\bmale\b", joined_text, re.IGNORECASE):
        fields["Sex"] = "Male"
    elif re.search(r"\bfemale\b", joined_text, re.IGNORECASE):
        fields["Sex"] = "Female"
    elif re.search(r"\bSEX[:\s]*M\b", joined_text):
        fields["Sex"] = "Male"
    elif re.search(r"\bSEX[:\s]*F\b", joined_text):
        fields["Sex"] = "Female"

    # Country of Birth → match line that contains birth location
    for line in lines:
        if "birth" in line.lower():
            code = re.search(r"\b[A-Z]{3}\b", line)
            if code:
                fields["Country of Birth"] = code.group()
            else:
                fields["Country of Birth"] = fields["Nationality"]
            break
    if not fields["Country of Birth"]:
        fields["Country of Birth"] = fields["Nationality"]

    # Issuing State → try to extract, otherwise use nationality
    for line in lines:
        if any(kw in line.lower() for kw in ["authority", "repubblica", "ministry", "issued by"]):
            code_match = re.search(r"\b[A-Z]{3}\b", line)
            if code_match:
                fields["Issuing State"] = code_match.group()
    if not fields["Issuing State"]:
        fields["Issuing State"] = fields["Nationality"]

    # Name Detection
    excluded_keywords = [
        "passport", "passaporto", "authority", "repubblica", "document",
        "birth", "expiry", "number", "code", "nationality", "sex", "issued"
    ]
    name_lines = []
    for line in lines:
        if (
            line.isupper()
            and line.replace(" ", "").isalpha()
            and not any(kw in line.lower() for kw in excluded_keywords)
            and len(line.split()) >= 1
            and not re.match(r"^[A-Z]{2,4}$", line.strip())
        ):
            name_lines.append(line.title())

    if len(name_lines) >= 2:
        fields["Family Name"] = name_lines[0]
        fields["Given Names"] = name_lines[1]
    elif len(name_lines) == 1:
        fields["Given Names"] = name_lines[0]

    return fields

# Upload UI
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

# Download Excel
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
