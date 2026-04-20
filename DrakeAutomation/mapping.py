# Mapping labels for JSON fields
from datetime import date, datetime

W2_BOX_TO_FIELD_LABELS ={
    "FormType": {"label": "Form Type"},
    # "TS": {"label": "TS"},
    "TaxYear": {"label":"Tax Year"},
    "Employer": {
        "EIN": {"label":"EIN"},
        "Name": "Name",
        "Street": "Street",
        "City": "City",
        "State": "State",
        "ZIP": "ZIP"
    },
    "Employee": {
        "SSN": "SSN"
    },
    "Entries": {
        "box1": {
            "label": "Wages, tips, other compensation"
        },
        "box2": {
          "label": "Federal income tax withheld"
        },
        "box3": {
          "label": "Social security wages"
        },
        "box4": {
          "label": "Social security tax withheld"
        },
        "box5": {
          "label": "Medicare wages and tips"
        },
        "box6": {
          "label": "Medicare tax withheld"
        },
        "box7": {
          "label": "Social security tips"
        },
        "box8": {
          "label": "Allocated tips"
        },
        "box10": {
          "label": "Dependent care benefits"
        },
        "box11": {
          "label": "Nonqualified plans"
        },
        "box14": {
          "label": "Other"
        },
        "box12": [
          {
            "LetterCode": {
              "label": "Letter Code"
            },
            "Amount": {
              "label": "Amount"
            }
          }
        ],
        "TaxInfos": [
            {
                "State": {
                    "label": "State"
                },
                "IdNumber": {
                    "label": "Employer's state ID number"
                },
                "box16": {
                    "label": "State wages, tips, etc."
                },
                "box17": {
                    "label": "State income tax"
                },
                "box18": {
                    "label": "Local wages, tips, etc."
                },
                "box19": {
                    "label": "Local income tax"
                },
                "box20": {
                    "label": "Locality name"
                }
            }
        ]
    }
}

DIV1099_BOX_TO_FIELD_LABELS = {
    "FormType": {"label": "Form Type"},
    # "TSJ": {"label": "TSJ"},
    "TaxYear": {"label":"Tax Year"},
    "Payer": {
        "TIN": {"label":"TIN"},
        "Name": {"label": "Name"},
        "Street": {"label": "Street"},
        "City": {"label": "City"},
        "State": {"label": "State"},
        "ZIP": {"label": "ZIP"},
        "PhoneNumber": {"label": "Phone Number"},
    },
    "Recipient":{
        "TIN": {"label":"TIN"},
        "Name": {"label":"Name"},
        "Street": {"label": "Street"},
        "City": {"label": "City"},
        "State": {"label": "State"},
        "ZIP": {"label": "ZIP"},
        "AccountNumber": {"label":"Account Number"},
    },
    "Entries": {
    "Box1a": {"label": "Total ordinary dividends"},
    "Box1b": {"label": "Qualified dividends"},
    "Box2a": {"label": "Total capital gain distr."},
    "Box2b": {"label": "Unrecap. Sec. 1250 gain"},
    "Box2c": {"label": "Section 1202 gain"},
    "Box2d": {"label": "Collectibles (28%) gain"},
    "Box2e": {"label": "Section 897 ordinary dividends"},
    "Box2f": {"label": "Section 897 capital gain"},
    "Box3": {"label": "Nondividend distributions"},
    "Box4": {"label": "Federal income tax withheld"},
    "Box5": {"label": "Section 199A dividends"},
    "Box6": {"label": "Investment expenses"},
    "Box7": {"label": "Foreign tax paid"},
    "Box8": {"label": "Foreign country or U.S. possession"},
    "Box9": {"label": "Cash liquidation distributions"},
    "Box10": {"label": "Noncash liquidation distributions"},
    "Box12": {"label": "Exempt-interest dividends"},
    "Box13": {"label": "Specified private activity bond interest dividends"},
    "TaxInfos": [
      {
        "Box14": {
          "label": "State"
        },
        "Box15": {
            "label": "State identification no."
        },
        "Box16": {
            "label": "State tax withheld"
        },
      }
    ]
    }
}

INT1099_BOX_TO_FIELD_LABELS = {
    "FormType": {"label": "Form Type"},
    # "TSJ": {"label": "TSJ"},
    "TaxYear": {"label": "Tax Year"},
    "Payer": {
        "TIN": {"label": "TIN"},
        "Name": {"label": "Name"},
        "Street": {"label": "Street"},
        "City": {"label": "City"},
        "State": {"label": "State"},
        "ZIP": {"label": "ZIP"},
        "PhoneNumber": {"label": "Phone Number"},
        "RTN": {"label": "RTN"},
    },
    "Recipient": {
        "TIN": {"label": "TIN"},
        "Name": {"label": "Name"},
        "Street": {"label": "Street"},
        "City": {"label": "City"},
        "State": {"label": "State"},
        "ZIP": {"label": "ZIP"},
        "AccountNumber": {"label": "Account Number"},
    },
    "Entries": {
        "Box1": {"label": "Interest income"},
        "Box2": {"label": "Early withdrawal penalty"},
        "Box3": {"label": "Interest on U.S. Savings Bonds and Treas. obligations"},
        "Box4": {"label": "Federal income tax withheld"},
        "Box5": {"label": "Investment expenses"},
        "Box6": {"label": "Foreign tax paid"},
        "Box7": {"label": "Foreign country or U.S. territory"},
        "Box8": {"label": "Tax-exempt interest"},
        "Box9": {"label": "Specified private activity bond interest"},
        "Box10": {"label": "Market discount"},
        "Box11": {"label": "Bond premium"},
        "Box12": {"label": "Bond premium on Treasury obligations"},
        "Box13": {"label": "Bond premium on tax-exempt bond"},
        "Box14": {"label": "Tax-exempt and tax credit bond CUSIP no."},
        "TaxInfos": [
            {
                "Box15": {"label": "State"},
                "Box16": {"label": "State identification no."},
                "Box17": {"label": "State tax withheld"},
            }
        ]
    }
}

R1099_BOX_TO_FIELD_LABELS = {
    "FormType": {"label": "Form Type"},
    # "TS": {"label": "TS"},
    "TaxYear": {"label": "Tax Year"},
    "Payer": {
        "TIN": {"label": "TIN"},
        "Name": {"label": "Name"},
        "Street": {"label": "Street"},
        "City": {"label": "City"},
        "State": {"label": "State"},
        "ZIP": {"label": "ZIP"},
        "PhoneNumber": {"label": "Phone Number"},
    },
    "Recipient": {
        "TIN": {"label": "TIN"},
        "Name": {"label": "Name"},
        "Street": {"label": "Street"},
        "City": {"label": "City"},
        "State": {"label": "State"},
        "ZIP": {"label": "ZIP"},
        "AccountNumber": {"label": "Account Number"},
    },
    "Entries": {
        "box1": {"label": "Gross distribution"},
        "box2a": {"label": "Taxable amount"},
        "box2b": {"label": "Taxable amount not determined"},
        "box3": {"label": "Capital gain (included in box 2a)"},
        "box4": {"label": "Federal income tax withheld"},
        "box5": {"label": "Employee contributions/Designated Roth contributions or insurance premiums"},
        "box6": {"label": "Net unrealized appreciation in employer's securities"},
        "box7": {"label": "Distribution code(s)"},
        "box8": {"label": "Other"},
        "box9a": {"label": "Your percentage of total distribution"},
        "box9b": {"label": "Total employee contributions"},
        "box10": {"label": "Amount allocable to IRR within 5 years"},
        "box11": {"label": "1st year of desig. Roth contrib."},
        "Box13": {"label": "Date of payment"},
        "TaxInfos": [
            {
                "box14": {"label": "State tax withheld"},
                "State": {"label": "State"},
                "PayerStateNumber": {"label": "Payer's state no."},
                "box16": {"label": "State distribution"},
                "box17": {"label": "Local tax withheld"},
                "box18": {"label": "Name of locality"},
                "box19": {"label": "Local distribution"},
            }
        ]
    }
}

SSA1099_BOX_TO_FIELD_LABELS = {
    "FormType": {"label": "Form Type"},
    # "TS": {"label": "TS"},
    "TaxYear": {"label": "Tax Year"},
    "Beneficiary": {
        "SSN": {"label": "Beneficiary's SSN"},
        "Name": {"label": "Name"},
        "Street": {"label": "Street"},
        "City": {"label": "City"},
        "State": {"label": "State"},
        "ZIP": {"label": "ZIP"},
        "ClaimNumber": {"label": "Claim Number"},
    },
    "Entries": {
        "box3": {"label": "Benefits paid in {TaxYear}"},
        "box4": {"label": "Benefits repaid to SSA in {PriorTaxYear}"},
        "box5": {"label": "Net benefits for {PriorTaxYear}"},
        "box6": {"label": "Voluntary federal income tax withheld"},
    }
}

FORM_FIELD_MAPPINGS = {
    "W2": W2_BOX_TO_FIELD_LABELS,
    "DIV": DIV1099_BOX_TO_FIELD_LABELS,
    "INT": INT1099_BOX_TO_FIELD_LABELS,
    "1099": R1099_BOX_TO_FIELD_LABELS,
    "SSA": SSA1099_BOX_TO_FIELD_LABELS,
}

def separate_state_local_tax_infos(mapped_data):
    """
    Separates TaxInfos into StateTaxInfos and LocalTaxInfos based on FormType.
    """
    if not isinstance(mapped_data, dict):
        return mapped_data

    entries = mapped_data.get("Entries")
    if not entries or not isinstance(entries, dict):
        return mapped_data

    tax_infos = entries.get("TaxInfos")
    if not tax_infos or not isinstance(tax_infos, list):
        return mapped_data

    form_type_obj = mapped_data.get("FormType")
    form_type = form_type_obj.get("value") if isinstance(form_type_obj, dict) else None

    state_tax_infos = []
    local_tax_infos = []

    for item in tax_infos:
        if not isinstance(item, dict):
            continue

        state_item = {}
        local_item = {}
        has_state = False
        has_local = False

        if form_type == "W2":
            # State: State, IdNumber, box16, box17
            for key in ["State", "IdNumber", "box16", "box17"]:
                if key in item:
                    state_item[key] = item[key]
                    has_state = True
            # Local: box18, box19, box20
            for key in ["box18", "box19", "box20"]:
                if key in item:
                    local_item[key] = item[key]
                    has_local = True

        elif form_type == "1099": # 1099-R
            # State: box14, State, PayerStateNumber, box16
            for key in ["box14", "State", "PayerStateNumber", "box16"]:
                if key in item:
                    state_item[key] = item[key]
                    has_state = True
            # Local: box17, box18, box19
            for key in ["box17", "box18", "box19"]:
                if key in item:
                    local_item[key] = item[key]
                    has_local = True
        
        elif form_type == "DIV":
            # State: Box14, Box15, Box16
            for key in ["Box14", "Box15", "Box16"]:
                if key in item:
                    state_item[key] = item[key]
                    has_state = True
        
        elif form_type == "INT":
            # State: Box15, Box16, Box17
            for key in ["Box15", "Box16", "Box17"]:
                if key in item:
                    state_item[key] = item[key]
                    has_state = True

        if has_state:
            state_tax_infos.append(state_item)
        if has_local:
            local_tax_infos.append(local_item)

    if state_tax_infos:
        entries["StateTaxInfos"] = state_tax_infos
    if local_tax_infos:
        entries["LocalTaxInfos"] = local_tax_infos

    return mapped_data

def map_fields_with_label_and_value(data, mapping=FORM_FIELD_MAPPINGS, context=None):
    result = {}

    if not isinstance(data, dict):
        return result

    # Handle data wrapped in "fields" key (common in Azure DI response)
    if "fields" in data and isinstance(data["fields"], dict):
        data = data["fields"]
        
    if context is None:
        context = {}
        
    # Extract TaxYear for dynamic label replacement
    if "TaxYear" not in context:
        tax_year_obj = data.get("TaxYear")
        if isinstance(tax_year_obj, dict):
            context["TaxYear"] = tax_year_obj.get("value")
        elif tax_year_obj:
             context["TaxYear"] = tax_year_obj
        
    if "TaxYear" in context and "PriorTaxYear" not in context and context["TaxYear"]:
        try:
            ty = int(str(context["TaxYear"]).strip())
            context["PriorTaxYear"] = str(ty - 1)
        except (ValueError, TypeError):
            pass

    detect_form = data.get("FormType", {}).get("value")
    mapping = FORM_FIELD_MAPPINGS.get(detect_form, mapping)

    for field, map_def in mapping.items():
        if field not in data:
            continue

        raw = data[field]
        value = raw.get("value") if isinstance(raw, dict) else raw

        if isinstance(value, (date, datetime)):
            value = value.isoformat()
        elif isinstance(value, bool):
            value = str(value)

        # map_def has a direct label
        if isinstance(map_def, dict) and "label" in map_def:
            label = map_def["label"]
            
            # Dynamic label replacement
            if "{TaxYear}" in label and context.get("TaxYear"):
                label = label.replace("{TaxYear}", str(context["TaxYear"]))
            if "{PriorTaxYear}" in label and context.get("PriorTaxYear"):
                label = label.replace("{PriorTaxYear}", str(context["PriorTaxYear"]))
                
            result[field] = {
                "label": label,
                "value": value
            }

        # Nested object mapping
        elif isinstance(map_def, dict):
            result[field] = map_fields_with_label_and_value(value, map_def, context)

        # map_def is a string (used as label)
        elif isinstance(map_def, str):
            label = map_def
            if "{TaxYear}" in label and context.get("TaxYear"):
                label = label.replace("{TaxYear}", str(context["TaxYear"]))
            if "{PriorTaxYear}" in label and context.get("PriorTaxYear"):
                label = label.replace("{PriorTaxYear}", str(context["PriorTaxYear"]))
                
            result[field] = {
                "label": label,
                "value": value
            }

        #  map_def is a list (e.g. Box12, TaxInfos)
        elif isinstance(map_def, list) and isinstance(value, list):
            item_mapping = map_def[0]
            result[field] = []

            for item in value:
                item_value = item.get("value") if isinstance(item, dict) else item
                result[field].append(
                    map_fields_with_label_and_value(item_value, item_mapping, context)
                )


    # Attempt to separate TaxInfos into State/Local tables if applicable
    result = separate_state_local_tax_infos(result)
    return result