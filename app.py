import streamlit as st
import requests
from PIL import Image
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import hashlib
import json
import io
import base64

# ---------- Google Sheets Setup ----------
@st.cache_resource
def connect_to_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["GcpCredentials"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open_by_url("https://docs.google.com/spreadsheets/d/1-_vm_JRPiOypRRDtp_xGCL7IyU5HKm_AgYSf2SXWxKo")

# ---------- Login Setup ----------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

users = {
    "admin": hash_password("admin123"),
    "user1": hash_password("password1")
}

def login():
    st.sidebar.title("Login")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        if username in users and users[username] == hash_password(password):
            st.session_state.logged_in = True
            st.session_state.username = username
        else:
            st.sidebar.error("Invalid username or password.")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login()
    st.stop()

username = st.session_state.username
st.sidebar.success(f"Logged in as: {username}")

# ---------- OCR.Space API ----------
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

# ---------- Extract Fields ----------
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

    for line in text.split("\n"):
        line = line.strip()
        if "Type" in line and ":" in line:
            fields["Document Type"] = line.split(":")[-1].strip()
        elif "No" in line and ":" in line:
            fields["Document Number"] = line.split(":")[-1].strip()
        elif "Nationality" in line and ":" in line:
            fields["Nationality"] = line.split(":")[-1].strip()
        elif "Surname" in line or "Family" in line:
            fields["Family Name"] = " ".join(line.split()[1:])
        elif "Given" in line:
            fields["Given Names"] = " ".join(line.split()[2:])
        elif "DOB" in line or "Date of Birth" in line:
            fields["Date of Birth"] = line.split(":")[-1].strip()
        elif "Sex" in line:
            fields["Sex"] = line.split(":")[-1].strip()
        elif "Country of Birth" in line:
            fields["Country of Birth"] = line.split(":")[-1].strip()
        elif "Issuing State" in line:
            fields["Issuing State"] = line.split(":")[-1].strip()
        elif "Document Expiry" in line or "Expire Date" in line:
            fields["Document Expiry Date"] = line.split(":")[-1].strip()

    return fields

# ---------- UI ----------
st.title("📸 OCR Data Extractor to Google Sheets")
uploaded_images = st.file_uploader("Upload image(s)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
show_raw = st.checkbox("Show OCR raw text")

if uploaded_images:
    new_data = []
    for img in uploaded_images:
        image = Image.open(img)
        text = extract_text_from_image(image)
        fields = extract_fields(text)
        new_data.append(fields)
        st.subheader(f"Extracted from {img.name}")
        st.json(fields)
        if show_raw:
            st.text_area("Raw OCR Text", text, height=100)

    df = pd.DataFrame(new_data)

    # Download button
    st.download_button("⬇️ Download CSV", df.to_csv(index=False), file_name="ocr_data.csv")

    # Save to Google Sheets
    if st.button("📤 Save to Google Sheets"):
        sheet = connect_to_sheet()
        try:
            worksheet = sheet.worksheet(username)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=username, rows="1000", cols="20")
            worksheet.append_row(list(df.columns))

        existing = worksheet.get_all_values()
        existing_df = pd.DataFrame(existing[1:], columns=existing[0]) if existing else pd.DataFrame(columns=df.columns)
        combined = pd.concat([existing_df, df], ignore_index=True).drop_duplicates(subset=["Document Number"])
        worksheet.clear()
        worksheet.append_row(list(df.columns))
        for row in combined.values.tolist():
            worksheet.append_row(row)

        st.success("✅ Data saved successfully.")

