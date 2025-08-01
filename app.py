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

    # Nationality (3-letter ISO)
    nationality = re.search(r"\b(ITA|EGY|USA|IND|FRA|DEU|ESP|CAN|KSA|UAE|QAT)\b", joined_text)
    if nationality:
        fields["Nationality"] = nationality.group()

    # Dates: use earliest as DOB, latest as Expiry
    all_dates = re.findall(r"\d{2}[\s/-]?[A-Z]{3}(?:[\s/-]?[A-Z]{3})?[\s/-]?\d{4}", joined_text)
    normalized_dates = [normalize_date(d) for d in all_dates]
    if normalized_dates:
        fields["Date of Birth"] = normalized_dates[0]
    if len(normalized_dates) > 1:
        fields["Expiry Date"] = normalized_dates[-1]

    # Sex detection
    if re.search(r"\bmale\b", joined_text, re.IGNORECASE):
        fields["Sex"] = "Male"
    elif re.search(r"\bfemale\b", joined_text, re.IGNORECASE):
        fields["Sex"] = "Female"
    elif re.search(r"\bSEX[:\s]*M\b", joined_text):
        fields["Sex"] = "Male"
    elif re.search(r"\bSEX[:\s]*F\b", joined_text):
        fields["Sex"] = "Female"

    # Country of Birth
    for line in lines:
        if "maracaibo" in line.lower() or "birth" in line.lower():
            fields["Country of Birth"] = line.title()
            break

    # Issuing State
    for line in lines:
        if any(kw in line.lower() for kw in ["authority", "repubblica", "ministry", "issued by"]):
            code_match = re.search(r"\b[A-Z]{3}\b", line)
            if code_match:
                fields["Issuing State"] = code_match.group()
    if not fields["Issuing State"]:
        fields["Issuing State"] = fields["Nationality"]

    # Name detection
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
            and not re.match(r"^[A-Z]{2,4}$", line.strip())  # avoid "ITA", "USA"
        ):
            name_lines.append(line.title())

    if len(name_lines) >= 2:
        fields["Family Name"] = name_lines[0]
        fields["Given Names"] = name_lines[1]
    elif len(name_lines) == 1:
        fields["Given Names"] = name_lines[0]

    return fields
