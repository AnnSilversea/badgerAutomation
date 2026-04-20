
def find_page_map(pages):
    """
    pages: list of { page_number: int, text: str }
    """
    page_map = {
        "page1": None,
        "schedule_l": None,
        "schedule_m1": None,
        "schedule_m2": None,
    }

    for p in pages:
        t = (p.get("text") or "").lower()
        n = p.get("page_number")

        if page_map["page1"] is None:
            if ("form 1120-s" in t and "income" in t and "deductions" in t):
                page_map["page1"] = n

        # Detect Form 1040 main page
        # common markers: "form 1040", "u.s. individual income tax return", "adjusted gross income"
        if "form 1040" in t or "u.s. individual income tax return" in t:
            # prefer to set a distinct key for 1040 main page if exists
            page_map.setdefault("form_1040_page", None)
            if page_map.get("form_1040_page") is None:
                page_map["form_1040_page"] = n

        # Detect common attached forms: W-2 and 1099 variants
        # We'll store lists of page numbers for each type
        # if "w-2" in t or "w2" in t:
        if "wage and tax statement" in t or "form w-2" in t:
            page_map.setdefault("w2_pages", [])
            if n not in page_map["w2_pages"]:
                page_map["w2_pages"].append(n)

        # if "1099-int" in t or "1099 int" in t or "interest income" in t:
        if "1099-int" in t or "1099 int" in t:
            page_map.setdefault("1099_int_pages", [])
            if n not in page_map["1099_int_pages"]:
                page_map["1099_int_pages"].append(n)

        # if "1099-div" in t or "1099 div" in t or "dividend" in t:
        if "1099-div" in t or "1099 div" in t:
            page_map.setdefault("1099_div_pages", [])
            if n not in page_map["1099_div_pages"]:
                page_map["1099_div_pages"].append(n)

        if "1099-nec" in t or "1099 nec" in t:
        # if "1099-nec" in t or "1099 nec" in t or "nonemployee" in t:
            page_map.setdefault("1099_nec_pages", [])
            if n not in page_map["1099_nec_pages"]:
                page_map["1099_nec_pages"].append(n)

        # if "1099-ssa" in t or "1099 ssa" in t or "social security" in t:
        if "1099-ssa" in t or "1099 ssa" in t:
            page_map.setdefault("1099_ssa_pages", [])
            if n not in page_map["1099_ssa_pages"]:
                page_map["1099_ssa_pages"].append(n)

        # if "1099-r" in t or "1099 r" in t or "distribution" in t:
        if "1099-r" in t or "1099 r" in t:
            page_map.setdefault("1099_r_pages", [])
            if n not in page_map["1099_r_pages"]:
                page_map["1099_r_pages"].append(n)

        if page_map["schedule_l"] is None:
            if ("schedule l" in t and "balance sheets per books" in t):
                page_map["schedule_l"] = n

        if page_map["schedule_m1"] is None:
            if ("schedule m-1" in t ):
                page_map["schedule_m1"] = n

        if page_map["schedule_m2"] is None:
            if ("schedule m-2" in t ):
                page_map["schedule_m2"] = n

    return page_map

