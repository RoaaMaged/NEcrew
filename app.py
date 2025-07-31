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

    # MRZ-style 3-letter country codes
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
        # Add more as needed
    }

    for line in text.split("\n"):
        line = line.strip().lower()

        if "type" in line and ":" in line:
            value = line.split(":")[-1].strip()
            fields["Document Type"] = "P" if "passport" in value.lower() else value
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
