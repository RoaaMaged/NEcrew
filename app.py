import streamlit as st
import os
import json
import cv2
import matplotlib.image as mpimg
from passporteye import read_mrz
import easyocr
from dateutil import parser
import string
import tempfile
import warnings
warnings.filterwarnings("ignore")

# Load OCR reader
reader = easyocr.Reader(['en'], gpu=False)

# Load country codes
with open("country_codes.json") as f:
    country_codes = json.load(f)

# Utility functions
def parse_date(string, iob=True):
    date = parser.parse(string, yearfirst=True).date() 
    return date.strftime('%d/%m/%Y')

def clean(text):
    return ''.join(i for i in text if i.isalnum()).upper()

def get_country_name(code):
    for country in country_codes:
        if country["alpha-3"] == code:
            return country["name"].upper()
    return code

def get_sex(code):
    if code in ['M', 'm', 'F', 'f']:
        return code.upper()
    elif code == '0':
        return 'M'
    return 'F'

def extract_passport_data(image_path):
    mrz = read_mrz(image_path, save_roi=True)
    if not mrz:
        return None

    roi_path = os.path.join(tempfile.gettempdir(), "mrz.png")
    mpimg.imsave(roi_path, mrz.aux["roi"], cmap="gray")

    img = cv2.imread(roi_path)
    img = cv2.resize(img, (1110, 140))

    allowlist = string.ascii_letters + string.digits + "< "
    codes = reader.readtext(img, paragraph=False, detail=0, allowlist=allowlist)

    if len(codes) < 2:
        return None

    a, b = codes[0].upper(), codes[1].upper()
    a = a + '<' * (44 - len(a)) if len(a) < 44 else a
    b = b + '<' * (44 - len(b)) if len(b) < 44 else b

    surname_names = a[5:44].split("<<", 1)
    surname, names = surname_names[0], surname_names[1] if len(surname_names) > 1 else ""

    data = {
        "Name": names.replace("<", " ").strip().upper(),
        "Surname": surname.replace("<", " ").strip().upper(),
        "Sex": get_sex(clean(b[20])),
        "Date of Birth": parse_date(b[13:19]),
        "Nationality": get_country_name(clean(b[10:13])),
        "Passport Type": clean(a[0:2]),
        "Passport Number": clean(b[0:9]),
        "Issuing Country": get_country_name(clean(a[2:5])),
        "Expiration Date": parse_date(b[21:27]),
        "Personal Number": clean(b[28:42]),
    }

    return data

# Streamlit UI
st.set_page_config(page_title="Passport OCR App", layout="centered")
st.title("🛂 Passport OCR Extractor")

uploaded_file = st.file_uploader("Upload a passport image (JPEG or PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp:
        temp.write(uploaded_file.read())
        temp_path = temp.name

    st.image(temp_path, caption="Uploaded Passport Image", use_column_width=True)
    st.write("🔍 Extracting data...")

    extracted = extract_passport_data(temp_path)
    if extracted:
        st.success("✅ Extraction successful!")
        st.table(extracted)
    else:
        st.error("❌ Could not extract data from the image.")
