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

    # --- Regex-based Extraction ---
    passport_no = re.search(r"\b([A-Z]{1,2}\d{6,9})\b", joined_text)
    if passport_no:
        fields["Passport Number"] = passport_no.group()

    dob = re.search(r"\b\d{2}[\s/-]?[A-Z]{3}[\s/-]?\d{4}\b", joined_text)
    if dob:
        fields["Date of Birth"] = dob.group().replace(" ", "/").replace("-", "/")

    expiry = re.findall(r"\d{2}[\s/-]?[A-Z]{3}[\s/-]?\d{4}", joined_text)
    if len(expiry) > 1:
        fields["Expiry Date"] = expiry[-1].replace(" ", "/").replace("-", "/")

    nationality = re.search(r"\bITA|EGY|USA|IND|FRA|DEU|ESP|CAN|KSA|UAE|QAT\b", joined_text)
    if nationality:
        fields["Nationality"] = nationality.group()

    if "male" in joined_text.lower():
        fields["Sex"] = "Male"
    elif "female" in joined_text.lower():
        fields["Sex"] = "Female"
    elif re.search(r"\bM\b", joined_text):
        fields["Sex"] = "Male"
    elif re.search(r"\bF\b", joined_text):
        fields["Sex"] = "Female"

    # Extract names heuristically
    possible_names = []
    for line in lines:
        if line.isupper() and 2 <= len(line.split()) <= 4 and all(len(w) > 2 for w in line.split()):
            possible_names.append(line.title())

    if len(possible_names) >= 2:
        fields["Family Name"] = possible_names[0]
        fields["Given Names"] = possible_names[1]
    elif len(possible_names) == 1:
        fields["Given Names"] = possible_names[0]

    # Country of birth (heuristic)
    birth_matches = re.findall(r"\b[A-Z]{3}\b", joined_text)
    if birth_matches:
        fields["Country of Birth"] = birth_matches[-1]
        fields["Issuing State"] = birth_matches[0]

    return fields

# Upload logic
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

# Download as Excel
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
