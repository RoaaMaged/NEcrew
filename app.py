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

# Normalize to DD-MMM-YY
def format_date(date_string):
    try:
        date_obj = datetime.strptime(date_string.strip(), "%d %b %Y")
        return date_obj.strftime("%d-%b-%y")
    except:
        return ""

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

    # Dates
    all_dates = re.findall(r"\d{2}[\s/-]?[A-Z]{3}(?:[\s/-]?[A-Z]{3})?[\s/-]?\d{4}", joined_text.upper())
    parsed_dates = []
    for d in all_dates:
        d_clean = re.sub(r"[/-]", " ", d.upper())
        d_clean = re.sub(r"\s+", " ", d_clean.strip())
        try:
            parsed = datetime.strptime(d_clean, "%d %b %Y")
            parsed_dates.append(parsed)
        except:
            continue

    parsed_dates.sort()
    if parsed_dates:
        fields["Date of Birth"] = parsed_dates[0].strftime("%d-%b-%y")
    if len(parsed_dates) >= 2:
        fields["Issuing Date"] = parsed_dates[1].strftime("%d-%b-%y")
    if len(parsed_dates) >= 3:
        fields["Expiry Date"] = parsed_dates[-1].strftime("%d-%b-%y")

    # Sex
    if re.search(r"\bmale\b", joined_text, re.IGNORECASE):
        fields["Sex"] = "Male"
    elif re.search(r"\bfemale\b", joined_text, re.IGNORECASE):
        fields["Sex"] = "Female"
    elif re.search(r"\bSEX[:\s]*M\b", joined_text):
        fields["Sex"] = "Male"
    elif re.search(r"\bSEX[:\s]*F\b", joined_text):
        fields["Sex"] = "Female"

    # Default Issuing State = Country of Birth = Nationality
    fallback_country = fields["Nationality"] or "—"
    fields["Issuing State"] = fallback_country
    fields["Country of Birth"] = fallback_country

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
