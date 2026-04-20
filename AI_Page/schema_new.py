"""
Schema for structured tax form extraction from filtered text.
Designed specifically for Page 1, Schedule L, M-1, M-2.
"""

SCHEMA_DEFINITION = {
    "document_type": {
        "description": "Primary tax form type (1120-S, 1120, 1065, 1040, unknown etc.)",
        "type": "string or null"
    },
    "tax_year": {
        "description": "Tax year ending date",
        "type": "string or null (format: YYYY or MM/DD/YYYY)"
    },
    "company": {
        "description": "Company/Organization information from Page 1",
        "type": "object",
        "fields": {
            "name": "string or null",
            "ein": "string or null (format: XX-XXXXXXX)",
            "address": "string or null",
            "city": "string or null",
            "state": "string or null (2-letter abbreviation)",
            "zip": "string or null"
        }
    },
    "clients": {
        "description": "List of all clients/taxpayers found in the document",
        "type": "list",
        "items": {
            "name": "string or null",
            "ssn": "string or null (format: XXX-XX-XXXX, MUST include hyphens)"
        }
    },
    "page_map": {
        "description": "Which PDF pages contain each section (auto-filled by backend)",
        "type": "object",
        "fields": {
            "page1": "number or null",
            "schedule_l": "number or null",
            "schedule_m1": "number or null",
            "schedule_m2": "number or null",
            "form_1040_page": "number or null",
            "w2_pages": "list of numbers or empty list",
            "1099_int_pages": "list of numbers or empty list",
            "1099_div_pages": "list of numbers or empty list",
            "1099_nec_pages": "list of numbers or empty list",
            "1099_ssa_pages": "list of numbers or empty list",
            "1099_r_pages": "list of numbers or empty list"
        }
    }
}
