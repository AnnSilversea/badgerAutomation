import re
from dataclasses import dataclass
import logging

log = logging.getLogger(__name__)

@dataclass
class TSDetectResult: 
    current_ts: str
    current_name: str
    index: int
    group_size: int
    search_client_id: str
    search_client_name: str


DEFAULT_TS_MAP = {
    "T": {
        "id": ["500001008", "500001007"],
        "name": ["LEEWARD CATAMARAN", "MEDIA BLOGGER"]
    },
    "S": {
        "id": ["400008008", "400008007"],
        "name": ["STARBOARD", "NICHE"]
    }
}

def get_val(obj, key, default=None):
    """Helper to extract value from OCR result which might be wrapped in 'value' dict"""
    if not obj or key not in obj:
        return default
    val = obj[key]
    if isinstance(val, dict) and "value" in val:
        return val["value"]
    return val

def normalize_id(id):
    """Remove non-numeric characters from ID"""
    if not id:
        return ""
    return re.sub(r'\D', '', str(id))

def normalize_phone(phone: str | None) -> str:
    """
    Handle OCR-normalized phone numbers like '+12223334444'
    and convert them back to Drake-compatible 10-digit US phone.
    """
    if not phone:
        return ""

    digits = re.sub(r"\D", "", phone)

    # OCR often converts US phone to +1XXXXXXXXXX
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    # Drake only accepts exactly 10 digits
    if len(digits) != 10:
        # log.warning(f"Phone number '{phone}' has {len(digits)} digits, expected 10. Skipping.")
        return ""

    return digits

def normalize_money(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return val
    val = str(val)
    val = re.sub(r"[^\d.\-]", "", val)
    try:
        return float(val)
    except ValueError:
        return None

def split_street_city(text):
    """
    Helper to split 'Street City' string based on street suffixes.
    Returns (Street, City)
    """
    suffix_pattern = r'\b(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Way|Court|Ct|Place|Pl|Parkway|Pkwy|Circle|Cir|Terrace|Ter|Square|Sq|Loop|Lp|Highway|Hwy)\.?\s+(?=[A-Za-z0-9])'
    matches = list(re.finditer(suffix_pattern, text, re.IGNORECASE))
    if matches:
        last_match = matches[-1]
        split_idx = last_match.end()
        if split_idx < len(text):
            return text[:split_idx].strip(), text[split_idx:].strip()
    return text, ""

def parse_address(address_str):
    """
    Analyzes address strings into Street, City, State, and ZIP codes.
    Supports common US address formats.
    """
    if not address_str:
        return {}
    
    result = {
        "Street": address_str,
        "City": "",
        "State": "",
        "ZIP": ""
    }
    
    # New logic: Prioritize line breaks (\n) if applicable.
    if "\n" in address_str:
        parts = address_str.split("\n", 1)
        result["Street"] = parts[0].strip()
        
        # The rest contains City, State, ZIP
        remaining = parts[1].strip()
        
        # 1. Separate the ZIP code.
        zip_match = re.search(r'\b(\d{5}(?:-\d{4})?)\b$', remaining)
        if zip_match:
            result["ZIP"] = zip_match.group(1)
            remaining = remaining[:zip_match.start()].strip()
            if remaining.endswith(","):
                remaining = remaining[:-1].strip()
        
        # 2. Separate State
        state_match = re.search(r'\b([A-Z]{2})\b$', remaining)
        if state_match:
            result["State"] = state_match.group(1)
            remaining = remaining[:state_match.start()].strip()
            if remaining.endswith(","):
                remaining = remaining[:-1].strip()
        
        # 3. The rest is City
        if remaining:
            result["City"] = remaining
        else:
            # If City is empty, it might be attached to Street (line 1).
            s, c = split_street_city(result["Street"])
            if c:
                result["Street"] = s
                result["City"] = c
        
        return result
    
    # Normalize line breaks to commas.
    addr = address_str.replace("\n", ", ").strip()
    
    # 1. Separate the ZIP code (the last 5 or 9 digits).
    zip_match = re.search(r'\b(\d{5}(?:-\d{4})?)\b$', addr)
    if zip_match:
        result["ZIP"] = zip_match.group(1)
        # Cut off the ZIP code from the chain.
        addr = addr[:zip_match.start()].strip()
        if addr.endswith(","):
            addr = addr[:-1].strip()
            
    # 2. Separate the State (the last two capital letters after removing the ZIP code).
    state_match = re.search(r'\b([A-Z]{2})\b$', addr)
    if state_match:
        result["State"] = state_match.group(1)
        addr = addr[:state_match.start()].strip()
        if addr.endswith(","):
            addr = addr[:-1].strip()
            
    # 3. separate City and Street.
    # Assumption: The part after the last comma is City
    if "," in addr:
        parts = addr.rsplit(",", 1)
        result["Street"] = parts[0].strip()
        result["City"] = parts[1].strip()
    else:
        # If there is no comma, try separating it with a suffix.
        s, c = split_street_city(addr)
        result["Street"] = s
        result["City"] = c
        
    # Fix: Check if City contains secondary unit (e.g. "Floor 6 Atlanta")
    city_val = result.get("City", "")
    if city_val:
        # Regex to catch: (Unit Type) (Number) (City Name)
        # e.g. "Floor 6 Atlanta", "Suite 100 New York"
        unit_pattern = r'^(Apt|Bldg|Floor|Fl|Suite|Ste|Unit|Room|Rm|Dept|#)\.?\s+([a-zA-Z0-9-]+)\s+(.+)$'
        match = re.match(unit_pattern, city_val, re.IGNORECASE)
        if match:
            real_city = match.group(3)
            unit_part = city_val[:match.start(3)].strip()
            
            result["Street"] = f"{result['Street']}, {unit_part}" if result["Street"] else unit_part
            result["City"] = real_city

    return result

def detect_current_ts_verbose(input_client_id: str, ts_map: dict = None) -> TSDetectResult | None:
    if ts_map is None:
        ts_map = DEFAULT_TS_MAP
        
    found_ts = None
    index = None
    current_name = ""

    # 1. Detect TS + index from ID in form
    for ts, val in ts_map.items():
        ids = val.get("id", []) if isinstance(val, dict) else val
        names = val.get("name", []) if isinstance(val, dict) else []

        if input_client_id in ids:
            found_ts = ts
            index = ids.index(input_client_id)
            if index < len(names):
                current_name = names[index]
            break

    if found_ts is None:
        return None

    # 2. RULE: Client ID to SEARCH:  "T"
    t_val = ts_map.get("T", {})
    t_ids = t_val.get("id", []) if isinstance(t_val, dict) else t_val
    t_names = t_val.get("name", []) if isinstance(t_val, dict) else []

    search_client_id = t_ids[index] if index < len(t_ids) else None
    search_client_name = t_names[index] if index < len(t_names) else None

    found_val = ts_map[found_ts]
    found_ids = found_val.get("id", []) if isinstance(found_val, dict) else found_val

    return TSDetectResult(
        current_ts=found_ts,
        current_name=current_name,
        index=index,
        group_size=len(found_ids),
        search_client_id=search_client_id,
        search_client_name=search_client_name
    )

def wrap_boxes(boxes: dict, except_keys: list = None):
    wrapped = {}
    for k, v in boxes.items():
        if v is None:
            continue
        if except_keys and k in except_keys:
            wrapped[k] = v
            continue
        
        wrapped[k] = {"value": v}
    return wrapped

# ========================== Normalize DIV 1099 ==========================

def normalize_1099_div(ocr_result):
    """
    Convert Azure OCR results to input format for Drake Automation.
    """
    fields = ocr_result.get("fields", {})
    
    # 1. Payer Information
    payer_raw = get_val(fields, "Payer")
    payer_data = {}
    if payer_raw:
        payer_data["TIN"] = normalize_id(get_val(payer_raw, "TIN"))
        payer_data["Name"] = get_val(payer_raw, "Name")
        payer_data["PhoneNumber"] = normalize_phone(get_val(payer_raw, "PhoneNumber")) 
        
        # Process the Payer address.
        addr_str = get_val(payer_raw, "Address")
        parsed_addr = parse_address(addr_str)
        payer_data.update(parsed_addr)
        
    # 2. Recipient Information
    recipient_raw = get_val(fields, "Recipient")
    recipient_data = {}
    
    ts = ""
    if recipient_raw:
        
        recipient_data["Name"] = get_val(recipient_raw, "Name")
        recipient_data["TIN"] = normalize_id(get_val(recipient_raw, "TIN"))
        
        result = detect_current_ts_verbose(recipient_data["TIN"])
        if result:
            ts = result.current_ts
        
        # Recipient address handling
        addr_str = get_val(recipient_raw, "Address")
        parsed_addr = parse_address(addr_str)
        recipient_data.update(parsed_addr)
        
        recipient_data["AccountNumber"] = get_val(recipient_raw, "AccountNumber")

    # 3. Transactions (Single Entry)
    transactions_raw = get_val(fields, "Transactions", [])

    txn_norm = {}

    if transactions_raw:
        item = transactions_raw[0]
        txn_val = (
            item.get("value")
            if isinstance(item, dict) and "value" in item
            else item
        )

        if not isinstance(txn_val, dict):
            txn_val = {}

        for k, v in txn_val.items():
            if k in ["CompanyPaidFees", "CompanyPaidServiceCharges", "ReinvestmentDiscount"]:
                continue

            if k == "StateTaxesWithheld":
                st_list = v.get("value") if isinstance(v, dict) else v
                st_norm_list = []

                if st_list:
                    for st_item in st_list:
                        st_val = (
                            st_item.get("value")
                            if isinstance(st_item, dict) and "value" in st_item
                            else st_item
                        )
                        if st_val:
                            st_row = {}
                            for sk, sv in st_val.items():
                                val_inner = sv.get("value") if isinstance(sv, dict) else sv
                                if sk == "Box16":
                                    val_inner = normalize_money(val_inner)
                                st_row[sk] = {"value": val_inner}
                            st_norm_list.append({"value": st_row})

                txn_norm["TaxInfos"] = st_norm_list
            else:
                val = v.get("value") if isinstance(v, dict) else v
                if k not in ["Box8"]:
                    val = normalize_money(val)
                txn_norm[k] = {"value": val}


    # Final unified structure
    final_fields = {
        "FormType": {"value": "DIV"},
        # "TSJ": {"value": ts},
        "TaxYear": {"value": get_val(fields, "TaxYear")},
        "Payer": {"value": payer_data},
        "Recipient": {"value": recipient_data},
        "Entries": {
            "value": txn_norm
        }
    }

    return {"fields": final_fields}

# ========================== Normalize INT 1099 ==========================

def normalize_1099_int(ocr_result):
    """
    Convert Azure OCR results to input format for Drake Automation (1099-INT).
    """
    fields = ocr_result.get("fields", {})

    # ---------- Payer ----------
    payer_raw = get_val(fields, "Payer")
    payer_data = {}
    if payer_raw:
        payer_data["TIN"] = normalize_id(get_val(payer_raw, "TIN"))
        payer_data["Name"] = get_val(payer_raw, "Name")
        payer_data.update(parse_address(get_val(payer_raw, "Address")))
        payer_data["PhoneNumber"] = normalize_phone(get_val(payer_raw, "PhoneNumber"))
        payer_data["RTN"] = get_val(payer_raw, "Rtn")

    # ---------- Recipient ----------
    recipient_raw = get_val(fields, "Recipient")
    recipient_data = {}
    ts = ""

    if recipient_raw:
        recipient_data["Name"] = get_val(recipient_raw, "Name")
        recipient_data["TIN"] = normalize_id(get_val(recipient_raw, "TIN"))

        r = detect_current_ts_verbose(recipient_data["TIN"])
        if r:
            ts = r.current_ts

        recipient_data.update(parse_address(get_val(recipient_raw, "Address")))
        recipient_data["AccountNumber"] = get_val(recipient_raw, "AccountNumber")

    # ---------- Transactions ----------
    transactions_raw = get_val(fields, "Transactions", [])
    txn_norm = {}

    if transactions_raw:
        item = transactions_raw[0]
        txn_val = (
            item.get("value")
            if isinstance(item, dict) and "value" in item
            else item
        )

        if not isinstance(txn_val, dict):
            txn_val = {}

        for k, v in txn_val.items():
            if k == "IsFactaFilingRequired":
                continue

            # ---- State Taxes (match DIV schema) ----
            if k == "StateTaxesWithheld":
                st_list = v.get("value") if isinstance(v, dict) else v
                taxinfos = []

                if st_list:
                    for st_item in st_list:
                        st_val = (
                            st_item.get("value")
                            if isinstance(st_item, dict) and "value" in st_item
                            else st_item
                        )
                        if not st_val:
                            continue

                        row = {}
                        for sk, sv in st_val.items():
                            val_inner = sv.get("value") if isinstance(sv, dict) else sv
                            if sk == "Box17":
                                val_inner = normalize_money(val_inner)
                            row[sk] = {"value": val_inner}
                        taxinfos.append({"value": row})

                txn_norm["TaxInfos"] = taxinfos

            # ---- Regular Boxes ----
            else:
                val = v.get("value") if isinstance(v, dict) else v
                if k not in ["Box7", "Box14"]:
                    val = normalize_money(val)
                txn_norm[k] = {"value": val}

    # ---------- Final ----------
    final_fields = {
        "FormType": {"value": "INT"},
        # "TSJ": {"value": ts},
        "TaxYear": {"value": get_val(fields, "TaxYear")},
        "Payer": {"value": payer_data},
        "Recipient": {"value": recipient_data},
        "Entries": {
            "value": txn_norm
        }
    }

    return {"fields": final_fields}

# ========================== Normalize R 1099 ==========================

def normalize_1099_r(ocr_result: dict):
    fields = ocr_result.get("fields", ocr_result) # Fallback to root if 'fields' key doesn't exist

    # ---------- PAYER ----------
    payer_raw = get_val(fields, "Payer") or {}
    payer = {
        "TIN": normalize_id(get_val(payer_raw, "TIN")),
        "Name": get_val(payer_raw, "Name"),
        **parse_address(get_val(payer_raw, "Address")),
        "PhoneNumber": normalize_phone(get_val(payer_raw, "PhoneNumber"))
    }

    # ---------- RECIPIENT ----------
    recipient_raw = get_val(fields, "Recipient") or {}
    recipient = {
        "TIN": normalize_id(get_val(recipient_raw, "TIN")),
        "Name": get_val(recipient_raw, "Name"),
        **parse_address(get_val(recipient_raw, "Address")),
        "AccountNumber": get_val(recipient_raw, "AccountNumber")
    }

    # ---------- TS DETECT ----------
    ts = ""
    r = detect_current_ts_verbose(recipient["TIN"])
    if r:
        ts = r.current_ts

    # ---------- BOXES ----------
    boxes_source = get_val(fields, "Boxes", fields) # Use 'Boxes' key if present, else root fields
    
    boxes = {}

    # Helper to safely get value from boxes_source and normalize money if applicable
    def get_and_normalize_box_value(key, is_money=True):
        val = get_val(boxes_source, key)
        if is_money:
            return normalize_money(val)
        return val

    boxes['box1'] = get_and_normalize_box_value("Box1")
    boxes['box2a'] = get_and_normalize_box_value("Box2a")
    # Box2b is a checkbox, not a value to be filled in BOX_1_TO_13
    boxes['box3'] = get_and_normalize_box_value("Box3")
    boxes['box4'] = get_and_normalize_box_value("Box4")
    boxes['box5'] = get_and_normalize_box_value("Box5")
    boxes['box6'] = get_and_normalize_box_value("Box6")
    
    # Box 7: Distribution Code
    box7_val = get_and_normalize_box_value("Box7", is_money=False)
    if box7_val is not None:
        if isinstance(box7_val, float) and box7_val.is_integer():
            box7_str = str(int(box7_val))
        else:
            box7_str = str(box7_val).strip()
        
        # Check if it's a digit followed by a letter (e.g., "7A", "1B")
        match = re.match(r"^(\d+)([A-Z])$", box7_str, re.IGNORECASE)
        if match:
            # Split into two parts for two dropdowns
            boxes['box7'] = [match.group(1), match.group(2).upper()]
        else:
            # It's a single code, pass it as a single value.
            boxes['box7'] = box7_str
    else:
        boxes['box7'] = None

    box8_amount = get_and_normalize_box_value("Box8")
    box8_percentage = get_and_normalize_box_value("Box8Percentage", is_money=False) 
    
    # boxes['box8'] = [
    #     {
    #         "value":{
    #             "Amount": {"value": box8_amount},
    #             "Percentage": {"value": box8_percentage}
    #         }
    #     }
    # ]
    if box8_amount is not None or box8_percentage is not None:
        boxes['box8'] = [box8_amount, box8_percentage]
    else:
        boxes['box8'] = None

    boxes['box9a'] = get_and_normalize_box_value("Box9a", is_money=False)
    boxes['box9b'] = get_and_normalize_box_value("Box9b")
    boxes['box10'] = get_and_normalize_box_value("Box10")

    # Box 11: First year of Roth contribution (year, should be string)
    box11_val = get_and_normalize_box_value("Box11", is_money=False)
    if box11_val is not None:
        if isinstance(box11_val, float) and box11_val.is_integer():
            boxes['box11'] = str(int(box11_val))
        else:
            boxes['box11'] = str(box11_val).strip()
    else:
        boxes['box11'] = None

    # ---------- TAX INFOS ----------
    tax_rows = []
    
    state_taxes_raw = get_val(fields, "StateTaxesWithheld", [])
    local_taxes_raw = get_val(fields, "LocalTaxesWithheld", [])
            
    for row in range(2):
        row_data_state = state_taxes_raw[row] if row < len(state_taxes_raw) else {}
        row_data_local = local_taxes_raw[row] if row < len(local_taxes_raw) else {}
        
        box15 = get_val(row_data_state, "Box15", "")
        state_code = box15.split("/")[0] if box15 and "/" in box15 else None
        payer_state_number = box15.split("/")[1] if box15 and "/" in box15 else box15
        
        row_dict = {
            "box14": normalize_money(get_val(row_data_state, "Box14")),
            "State": state_code,
            "PayerStateNumber": payer_state_number,
            "box16": normalize_money(get_val(row_data_state, "Box16")),
            "box17": normalize_money(get_val(row_data_local, "Box17")),
            "box18": get_val(row_data_local, "Box18"),
            "box19": normalize_money(get_val(row_data_local, "Box19")),
        }
        if any(v is not None for v in row_dict.values()):
            tax_rows.append({"value": row_dict})
            

    final_fields = {
        "FormType": {"value": "1099"},
        # "TS": {"value": ts}, 
        "TaxYear": {"value": get_val(fields, "TaxYear")},
        "Payer": {"value": payer},
        "Recipient": {"value": recipient},
        "Entries": {
            "value": {
                **wrap_boxes(boxes, ["box7", "box8"]),
                "TaxInfos": tax_rows
            }
        }
    }

    return {"fields": final_fields}
    

# ========================== Normalize SSA 1099 ==========================

def normalize_1099_ssa(ocr_result: dict):
    fields = ocr_result.get("fields", ocr_result) # Fallback to root if 'fields' key doesn't exist

    # ---------- Payer (Static for SSA) ----------
    # payer = {
    #     "Name": "SOCIAL SECURITY ADMINISTRATION"
    # }

    # ---------- Beneficiary ---------
    beneficiary_raw = get_val(fields, "Beneficiary") or {}
    beneficiary = {
        "SSN": normalize_id(get_val(beneficiary_raw, "SSN")),
        "Name": get_val(beneficiary_raw, "Name"),
        **parse_address(get_val(beneficiary_raw, "Address")),
        "ClaimNumber": get_val(fields, "ClaimNumber")
    }

    # ---------- TS DETECT ----------
    ts = ""
    r = detect_current_ts_verbose(beneficiary["SSN"])
    if r:
        ts = r.current_ts

    # ---------- BOXES ----------
    boxes_source = get_val(fields, "Boxes", fields) # Use 'Boxes' key if present, else root fields
    
    boxes = {}

    # Helper to safely get value from boxes_source and normalize money if applicable
    def get_and_normalize_box_value(key, is_money=True):
        val = get_val(boxes_source, key)
        if is_money:
            return normalize_money(val)
        return val

    boxes['box3'] = get_and_normalize_box_value("Box3")
    boxes['box4'] = get_and_normalize_box_value("Box4")
    boxes['box5'] = get_and_normalize_box_value("Box5")
    boxes['box6'] = get_and_normalize_box_value("Box6")
        
    final_fields = {
        "FormType": {"value": "SSA"},
        # "TS": {"value": ts},
        "TaxYear": {"value": get_val(fields, "TaxYear")},
        "Beneficiary": {"value": beneficiary},
        "Entries": {
            "value": wrap_boxes(boxes)
        }
    }

    return {"fields": final_fields}

# ========================== Normalize W-2 ==========================

def normalize_w2(ocr_result: dict):
    """
    Convert Azure OCR results for W-2 to input format for Drake Automation.
    """
    fields = ocr_result.get("fields", ocr_result)

    # ---------- Payer (Employer) ----------
    employer_list = get_val(fields, "Employer", [])
    employer_raw = {}
    if employer_list:
        first_item = employer_list[0]
        employer_raw = first_item.get("value") if (isinstance(first_item, dict) and "value" in first_item) else first_item

    payer = {
        "EIN": normalize_id(get_val(employer_raw, "EIN")) ,
        "Name": get_val(employer_raw, "Name"),
        **parse_address(get_val(employer_raw, "Address"))
    }

    # ---------- Recipient (Employee) ----------
    ssn_raw = get_val(fields, "SSN")
    ssn_normalized = normalize_id(ssn_raw)
    
    # For W2, Recipient name is often not a separate field in OCR, but we create the object for consistency.
    recipient = {
        "SSN": ssn_normalized,
    }

    # ---------- TS DETECT ----------
    ts = ""
    r = detect_current_ts_verbose(ssn_normalized)
    if r:
        ts = r.current_ts

    # ---------- BOXES ----------
    boxes = {}
    # Simple boxes (1-11)
    box_keys = [f"box{i}" for i in range(1, 12)]
    for key in box_keys:
        raw_val = get_val(fields, key)
        if raw_val is not None:
            boxes[key] = {"value": normalize_money(raw_val)}

    # Box 14 (Text + Amount) - Do not normalize as money
    box14_val = get_val(fields, "box14")
    if box14_val is not None:
        boxes["box14"] = {"value": box14_val}

    # Box 12 (list of code/amount)
    box12_list = []
    box12_raw = get_val(fields, "box12", [])
    if box12_raw:
        for item in box12_raw:
            item_val = item.get("value") if (isinstance(item, dict) and "value" in item) else item
            code = get_val(item_val, 'LetterCode')
            amount = normalize_money(get_val(item_val, 'Amount'))
            if code and amount is not None:
                box12_list.append({"value": {"LetterCode": {"value": code}, "Amount": {"value": amount}}})
    if box12_list:
        boxes['box12'] = box12_list

    # ---------- TaxInfos (State/Local) ----------
    tax_infos = []
    tax_infos_raw = get_val(fields, "TaxInfos", [])
    if tax_infos_raw:
        for item in tax_infos_raw:
            item_val = item.get("value") if (isinstance(item, dict) and "value" in item) else item
            info = {
                "State": {"value": get_val(item_val, 'State')},
                "IdNumber": {"value": get_val(item_val, 'EmployerStateIdNumber') or get_val(item_val, 'IdNumber')},
                "box16": {"value": normalize_money(get_val(item_val, 'box16'))},
                "box17": {"value": normalize_money(get_val(item_val, 'box17'))},
                "box18": {"value": normalize_money(get_val(item_val, 'box18'))},
                "box19": {"value": normalize_money(get_val(item_val, 'box19'))},
                "box20": {"value": get_val(item_val, 'box20')},
            }
            if any(v.get('value') for k, v in info.items() if isinstance(v, dict)):
                tax_infos.append({"value": info})

    final_fields = {
        "FormType": {"value": "W2"},
        # "TS": {"value": ts},
        "TaxYear": {"value": get_val(fields, "TaxYear")},
        "Employer": {"value": payer},
        "Employee": {"value": recipient},
        "Entries": {
            "value": {
                **boxes,
                "TaxInfos": tax_infos
            }
        }
    }

    return {"fields": final_fields}