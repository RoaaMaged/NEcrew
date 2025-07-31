import streamlit as st
import pytesseract
from PIL import Image
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit_authenticator as stauth
import hashlib
import json

# ---------- Google Sheets Setup ----------
@st.cache_resource
def connect_to_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["GCP_CREDENTIALS"])
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

# ---------- OCR Logic ----------
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
        if "Document No" in line or "Document Number" in line:
            fields["Document Number"] = line.split()[-1]
        elif "Expiry" in line:
            fields["Document Expiry Date"] = line.split()[-1]
        elif "Nationality" in line:
            fields["Nationality"] = line.split()[-1]
        elif "Surname" in line or "Family" in line:
            fields["Family Name"] = " ".join(line.split()[1:])
        elif "Given" in line:
            fields["Given Names"] = " ".join(line.split()[2:])
        elif "DOB" in line or "Date of Birth" in line:
            fields["Date of Birth"] = line.split()[-1]
        elif "Sex" in line:
            fields["Sex"] = line.split()[-1]
        elif "Country of Birth" in line:
            fields["Country of Birth"] = line.split()[-1]
        elif "Issuing State" in line:
            fields["Issuing State"] = line.split()[-1]
        elif "Document Type" in line:
            fields["Document Type"] = line.split()[-1]
    return fields

# ---------- Streamlit UI ----------
st.title("📸 Document OCR to Google Sheets")
uploaded_images = st.file_uploader("Upload image(s)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_images:
    new_data = []
    st.subheader("🧾 Extracted Data")
    for image_file in uploaded_images:
        image = Image.open(image_file)
        text = pytesseract.image_to_string(image)
        fields = extract_fields(text)
        new_data.append(fields)
        st.write(f"**{image_file.name}**")
        st.json(fields)

    if st.button("📤 Save to Google Sheets"):
        columns = list(new_data[0].keys())
        new_df = pd.DataFrame(new_data, columns=columns)
        sheet = connect_to_sheet()
        try:
            worksheet = sheet.worksheet(username)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=username, rows="1000", cols="20")
            worksheet.append_row(columns)
        existing = worksheet.get_all_values()
        if existing:
            existing_df = pd.DataFrame(existing[1:], columns=existing[0])
        else:
            existing_df = pd.DataFrame(columns=columns)
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["Document Number"])
        worksheet.clear()
        worksheet.append_row(columns)
        for row in combined.values.tolist():
            worksheet.append_row(row)
        st.success("✅ Data saved to Google Sheet!")
