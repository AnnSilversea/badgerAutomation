"""
Field mappings for different form models
Maps field names (box keys) to Line, Label, and Value structure
"""
from typing import Dict, Any, Optional, List
import math
import re

W2_NUMERIC_FIELDS = {
    "box1",
    "box2",
    "box3",
    "box4",
    "box5",
    "box6",
    "box7",
    "box8",
    "box10",
    "box11",
}

STATE_LOCAL_NUMERIC_FIELDS = {
    "box16",
    "box17",
    "box18",
    "box19",
}


def _normalize_numeric_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if math.isfinite(value) else None
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if cleaned == "":
        return None
    cleaned = re.sub(r"[,\s$€£¥]", "", cleaned)
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    if cleaned in ("", ".", "-", "-."):
        return None
    is_negative = cleaned.startswith("-")
    cleaned = cleaned.replace("-", "")
    parts = cleaned.split(".")
    if len(parts) > 1:
        cleaned = f"{parts[0]}.{''.join(parts[1:])}"
    if is_negative:
        cleaned = f"-{cleaned}"
    try:
        num = float(cleaned)
    except ValueError:
        return None
    return num if math.isfinite(num) else None


def _format_two_decimal(value: Any) -> str:
    num = _normalize_numeric_value(value)
    if num is None:
        return "0.00"
    return f"{num:.2f}"

FORM_1120S = {
    "box1a": {"line": "1a", "label": "Gross receipts or sales"},
    "box1b": {"line": "1b", "label": "Returns and allowances"},
    "box1c": {"line": "1c", "label": "Balance"},
    "box2":  {"line": "2",  "label": "Cost of goods sold"},
    "box3":  {"line": "3",  "label": "Gross profit"},
    "box4":  {"line": "4",  "label": "Dividends and interest"},
    "box5":  {"line": "5",  "label": "Other income (attach statement)"},
    "box6":  {"line": "6",  "label": "Total income"},
    "box7":  {"line": "7",  "label": "Compensation of officers"},
    "box8":  {"line": "8",  "label": "Salaries and wages"},
    "box9":  {"line": "9",  "label": "Repairs and maintenance"},
    "box10": {"line": "10", "label": "Bad debts"},
    "box11": {"line": "11", "label": "Rents"},
    "box12": {"line": "12", "label": "Taxes and licenses"},
    "box13": {"line": "13", "label": "Interest"},
    "box14": {"line": "14", "label": "Depreciation"},
    "box15": {"line": "15", "label": "Depletion"},
    "box16": {"line": "16", "label": "Advertising"},
    "box17": {"line": "17", "label": "Pension, profit-sharing, etc."},
    "box18": {"line": "18", "label": "Employee benefit programs"},
    "box19": {"line": "19", "label": "Energy efficient commercial bldgs deduction"},
    "box20": {"line": "20", "label": "Other deductions (attach statement)"},
    "box21": {"line": "21", "label": "Total deductions"},
    "box22": {"line": "22", "label": "Taxable income (loss)"},
    "box23a": {"line": "23a", "label": "Excess net passive income tax"},
    "box23b": {"line": "23b", "label": "Tax from Schedule D"},
    "box23c": {"line": "23c", "label": "Add lines 23a and 23b"},
    "box24a": {"line": "24a", "label": "Estimated tax payments"},
    "box24b": {"line": "24b", "label": "Tax deposited with Form 7004"},
    "box24c": {"line": "24c", "label": "Credit for tax paid on fuels"},
    "box24d": {"line": "24d", "label": "Refundable credit from Form 3800"},
    "box24z": {"line": "24z", "label": "Other payments/credits"},
    "box25":  {"line": "25",  "label": "Total payments"},
    "box26":  {"line": "26",  "label": "Estimated tax penalty"},
    "box27":  {"line": "27",  "label": "Amount owed"},
    "box28":  {"line": "28",  "label": "Overpayment"},
}

Form_1120s_SCHEDULE_L_LINE = {
    "box1":  {"line": "1",  "label": "Cash"},
    "box2a": {"line": "2a", "label": "Trade notes and accounts receivable"},
    "box2b": {"line": "2b", "label": "Less allowance for bad debts"},
    "box3":  {"line": "3",  "label": "Inventories"},
    "box4":  {"line": "4",  "label": "U.S. government obligations"},
    "box5":  {"line": "5",  "label": "Tax-exempt securities"},
    "box6":  {"line": "6",  "label": "Other current assets (attach statement)"},
    "box7":  {"line": "7",  "label": "Loans to shareholders"},
    "box8":  {"line": "8",  "label": "Mortgage and real estate loans"},
    "box9":  {"line": "9",  "label": "Other investments (attach statement)"},
    "box10a":{"line": "10a","label": "Buildings and other depreciable assets"},
    "box10b":{"line": "10b","label": "Less accumulated depreciation"},
    "box11a":{"line": "11a","label": "Depletable assets"},
    "box11b":{"line": "11b","label": "Less accumulated depletion"},
    "box12": {"line": "12", "label": "Land"},
    "box13a":{"line": "13a","label": "Intangible assets"},
    "box13b":{"line": "13b","label": "Less accumulated amortization"},
    "box14": {"line": "14", "label": "Other assets"},
    "box15": {"line": "15", "label": "Total assets"},
    "box16": {"line": "16", "label": "Accounts payable"},
    "box17": {"line": "17", "label": "Notes payable < 1 year"},
    "box18": {"line": "18", "label": "Other current liabilities"},
    "box19": {"line": "19", "label": "Loans from shareholders"},
    "box20": {"line": "20", "label": "Notes payable ≥ 1 year"},
    "box21": {"line": "21", "label": "Other liabilities"},
    "box22": {"line": "22", "label": "Capital stock"},
    "box23": {"line": "23", "label": "Additional paid-in capital"},
    "box24": {"line": "24", "label": "Retained earnings"},
    "box25": {"line": "25", "label": "Equity adjustments"},
    "box26": {"line": "26", "label": "Less treasury stock"},
    "box27": {"line": "27", "label": "Total liabilities & equity"},
}

Form_1120s_SCHEDULE_M2_LINE = {
    "box1": {"line": "1", "label": "Balance at beginning of tax year"},
    "box2": {"line": "2", "label": "Ordinary income from page 1, line 22"},
    "box3": {"line": "3", "label": "Other additions (attach statement)"},
    "box4": {"line": "4", "label": "Loss from page 1, line 22"},
    "box5": {"line": "5", "label": "Other reductions (attach statement)"},
    "box6": {"line": "6", "label": "Combine lines 1 through 5"},
    "box7": {"line": "7", "label": "Distributions"},
    "box8": {"line": "8", "label": "Balance at end of tax year"},
}

Form_1120s_SCHEDULE_M1_LINE = {
    "box1": {"line": "1", "label": "Net income (loss) per books",},
    "box2": {"line": "2", "label": "Income included on Schedule K, lines 1, 2, 3, 4, 5a, 6, 7, 8a, 9, and 10, not recorded on books this year (itemize):",},
    "box3": {"line": "3","label": "Expenses recorded on books this year not included on Schedule K, lines 1 through 12e, and 16f (itemize):",},
    "box4": {"line": "4","label": "Add lines 1 through 3", },
    "box5": {"line": "5","label": "Income recorded on books this year not included on Schedule K, lines 1 through 10 (itemize):", },
    "box6": {"line": "6","label": "Deductions included on Schedule K, lines 1 through 12e, and 16f, not charged against book income this year (itemize):",},
    "box7": {"line": "7","label": "Add lines 5 and 6",},
    "box8": {"line": "8","label": "Income (loss) (Subtract line 7 from line 4)",},
}
BOX_TO_1120_LINE={
  "box1a": { "line": "1a", "label": "Gross receipts or sales" },
  "box1b": { "line": "1b", "label": "Returns and allowances" },
  "box1c": { "line": "1c", "label": "Balance. Subtract line 1b from line 1a" },
  "box2":  { "line": "2",  "label": "Cost of goods sold (attach Form 1125-A)" },
  "box3":  { "line": "3",  "label": "Gross profit. Subtract line 2 from line 1c" },
  "box4":  { "line": "4",  "label": "Dividends and inclusions (Schedule C, line 23)" },
  "box5":  { "line": "5",  "label": "Interest" },
  "box6":  { "line": "6",  "label": "Gross rents" },
  "box7":  { "line": "7",  "label": "Gross royalties" },
  "box8":  { "line": "8",  "label": "Capital gain net income (attach Schedule D (Form 1120))" },
  "box9":  { "line": "9",  "label": "Net gain (loss) from Form 4797, Part II, line 17 (attach Form 4797)" },
  "box10": { "line": "10", "label": "Other income (see instructions—attach statement)" },
  "box11": { "line": "11", "label": "Total income. Add lines 3 through 10" },
  "box12": { "line": "12", "label": "Compensation of officers (see instructions—attach Form 1125-E)" },
  "box13": { "line": "13", "label": "Salaries and wages (less employment credits)" },
  "box14": { "line": "14", "label": "Repairs and maintenance" },
  "box15": { "line": "15", "label": "Bad debts" },
  "box16": { "line": "16", "label": "Rents" },
  "box17": { "line": "17", "label": "Taxes and licenses" },
  "box18": { "line": "18", "label": "Interest (see instructions)" },
  "box19": { "line": "19", "label": "Charitable contributions" },
  "box20": { "line": "20", "label": "Depreciation from Form 4562 not claimed on Form 1125-A or elsewhere on return (attach Form 4562)" },
  "box21": { "line": "21", "label": "Depletion" },
  "box22": { "line": "22", "label": "Advertising" },
  "box23": { "line": "23", "label": "Pension, profit-sharing, etc., plans" },
  "box24": { "line": "24", "label": "Employee benefit programs" },
  "box25": { "line": "25", "label": "Energy efficient commercial buildings deduction (attach Form 7205)" },
  "box26": { "line": "26", "label": "Other deductions (attach statement)" },
  "box27": { "line": "27", "label": "Total deductions. Add lines 12 through 26" },
  "box28": { "line": "28", "label": "Taxable income before net operating loss deduction and special deductions. Subtract line 27 from line 11" },
  "box29a": { "line": "29a", "label": "Net operating loss deduction (see instructions)" },
  "box29b": { "line": "29b", "label": "Special deductions (Schedule C, line 24)" },
  "box29c": { "line": "29c", "label": "Add lines 29a and 29b" },
  "box30": { "line": "30", "label": "Taxable income. Subtract line 29c from line 28. See instructions" },
  "box31": { "line": "31", "label": "Total tax (Schedule J, line 12)" },
  "box32": { "line": "32", "label": "Reserved for future use" },
  "box33": { "line": "33", "label": "Total payments and credits (Schedule J, line 23)" },
  "box34": { "line": "34", "label": "Estimated tax penalty. See instructions. Check if Form 2220 is attached" },
  "box35": { "line": "35", "label": "Amount owed. If line 33 is smaller than the total of lines 31 and 34, enter amount owed" },
  "box36": { "line": "36", "label": "Overpayment. If line 33 is larger than the total of lines 31 and 34, enter amount overpaid" },
  "box37": { "line": "37", "label": "Enter amount from line 36 you want: Credited to 2025 estimated tax                Refunded" },
}


BOX_TO_1120_SCHEDULE_L_LINE={
  "box1":  { "line": "1",  "label": "Cash" },
  "box2a": { "line": "2a", "label": "Trade notes and accounts receivable" },
  "box2b": { "line": "2b", "label": "Less allowance for bad debts" },
  "box3":  { "line": "3",  "label": "Inventories" },
  "box4":  { "line": "4",  "label": "U.S. government obligations" },
  "box5":  { "line": "5",  "label": "Tax-exempt securities" },
  "box6":  { "line": "6",  "label": "Other current assets (attach statement)" },
  "box7":  { "line": "7",  "label": "Loans to shareholders" },
  "box8":  { "line": "8",  "label": "Mortgage and real estate loans" },
  "box9":  { "line": "9",  "label": "Other investments (attach statement)" },
  "box10a": { "line": "10a", "label": "Buildings and other depreciable assets" },
  "box10b": { "line": "10b", "label": "Less accumulated depreciation" },
  "box11a": { "line": "11a", "label": "Depletable assets" },
  "box11b": { "line": "11b", "label": "Less accumulated depletion" },
  "box12":  { "line": "12",  "label": "Land (net of any amortization)" },
  "box13a": { "line": "13a", "label": "Intangible assets (amortizable only)" },
  "box13b": { "line": "13b", "label": "Less accumulated amortization" },
  "box14":  { "line": "14",  "label": "Other assets (attach statement)" },
  "box15":  { "line": "15",  "label": "Total assets" },
  "box16":  { "line": "16",  "label": "Accounts payable" },
  "box17":  { "line": "17",  "label": "Mortgages, notes, bonds payable in less than 1 year" },
  "box18":  { "line": "18",  "label": "Other current liabilities (attach statement)" },
  "box19":  { "line": "19",  "label": "Loans from shareholders" },
  "box20":  { "line": "20",  "label": "Mortgages, notes, bonds payable in 1 year or more" },
  "box21":  { "line": "21",  "label": "Other liabilities (attach statement)" },
  "box22a": { "line": "22a", "label": "Capital stock — Preferred stock" },
  "box22b": { "line": "22b", "label": "Capital stock — Common stock" },
  "box23":  { "line": "23",  "label": "Additional paid-in capital" },
  "box24":  { "line": "24",  "label": "Retained earnings — Appropriated (attach statement)" },
  "box25":  { "line": "25",  "label": "Retained earnings — Unappropriated" },
  "box26":  { "line": "26",  "label": "Adjustments to shareholders' equity (attach statement)" },
  "box27":  { "line": "27",  "label": "Less cost of treasury stock" },
  "box28":  { "line": "28",  "label": "Total liabilities and shareholders' equity" }
}


BOX_TO_1120_SCHEDULE_M1_LINE={
  "box1": {"line": "1","label": "Net income (loss) per books"},
  "box2": {"line": "2","label": "Federal income tax per books"},
  "box3": {"line": "3","label": "Excess of capital losses over capital gains"},
  "box4": {"line": "4","label": "Income subject to tax not recorded on books this year (itemize):"},
  "box5": {"line": "5","label": "Expenses recorded on books this year not deducted on this return (itemize):"},
  "box6": {"line": "6","label": "Add lines 1 through 5"},
  "box7": {"line": "7","label": "Income recorded on books this year not included on this return (itemize) Tax-exempt interest:"},
  "box8": {"line": "8","label": "Deductions on this return not charged against book income this year (itemize):"},
  "box9": {"line": "9","label": "Add lines 7 and 8"},
  "box10": {"line": "10","label": "Income (page 1, line 28)—line 6 less line 9"}
}


BOX_TO_1120_SCHEDULE_M2_LINE={
  "box1": {"line": "1","label": "Balance at beginning of year"},
  "box2": {"line": "2","label": "Net income (loss) per books"},
  "box3": {"line": "3","label": "Other increases (itemize):"},
  "box4": {"line": "4","label": "Add lines 1, 2, and 3"},
  "box5a": {"line": "5a","label": "Distributions — Cash"},
  "box5b": {"line": "5b","label": "Distributions — Stock"},
  "box5c": {"line": "5c","label": "Distributions — Property"},
  "box6": {"line": "6","label": "Other decreases (itemize):"},
  "box7": {"line": "7","label": "Add lines 5 and 6"},
  "box8": {"line": "8","label": "Balance at end of year (line 4 less line 7)"}
}

BOX_TO_1065_LINE = {
    "box1a": {"line": "1a", "label": "Gross receipts or sales"},
    "box1b": {"line": "1b", "label": "Less returns and allowances"},
    "box1c": {"line": "1c", "label": "Balance"},
    "box2":  {"line": "2",  "label": "Cost of goods sold"},
    "box3":  {"line": "3",  "label": "Gross profit (loss)"},
    "box4":  {"line": "4",  "label": "Ordinary income (loss) from other partnerships, estates, and trusts"},
    "box5":  {"line": "5",  "label": "Net farm profit (loss)"},
    "box6":  {"line": "6",  "label": "Net gain (loss) from Form 4797"},
    "box7":  {"line": "7",  "label": "Other income (loss)"},
    "box8":  {"line": "8",  "label": "Total income (loss)"},
    "box9":   {"line": "9",  "label": "Salaries and wages (other than to partners)"},
    "box10":  {"line": "10", "label": "Guaranteed payments to partners"},
    "box11":  {"line": "11", "label": "Repairs and maintenance"},
    "box12":  {"line": "12", "label": "Bad debts"},
    "box13":  {"line": "13", "label": "Rent"},
    "box14":  {"line": "14", "label": "Taxes and licenses"},
    "box15":  {"line": "15", "label": "Interest"},
    "box16a": {"line": "16a", "label": "Depreciation (Form 4562)"},
    "box16b": {"line": "16b", "label": "Less depreciation reported on Form 1125-A and elsewhere"},
    "box16c": {"line": "16c", "label": "Depreciation"},
    "box17":  {"line": "17", "label": "Depletion (not oil and gas)"},
    "box18":  {"line": "18", "label": "Retirement plans, etc."},
    "box19":  {"line": "19", "label": "Employee benefit programs"},
    "box20":  {"line": "20", "label": "Energy efficient commercial buildings deduction"},
    "box21":  {"line": "21", "label": "Other deductions"},
    "box22":  {"line": "22", "label": "Total deductions"},
    "box23":  {"line": "23", "label": "Ordinary business income (loss)"},
}

BOX_TO_1065_SCHEDULE_L_LINE = {
    "box1":  {"line": "1",  "label": "Cash"},
    "box2a": {"line": "2a", "label": "Trade notes and accounts receivable"},
    "box2b": {"line": "2b", "label": "Less allowance for bad debts"},
    "box3":  {"line": "3",  "label": "Inventories"},
    "box4":  {"line": "4",  "label": "U.S. government obligations"},
    "box5":  {"line": "5",  "label": "Tax-exempt securities"},
    "box6":  {"line": "6",  "label": "Other current assets (attach statement)"},
    "box7a": {"line": "7a", "label": "Loans to partners (or persons related to partners)"},
    "box7b": {"line": "7b", "label": "Mortgage and real estate loans"},
    "box8":  {"line": "8",  "label": "Other investments (attach statement)"},
    "box9a": {"line": "9a", "label": "Buildings and other depreciable assets"},
    "box9b": {"line": "9b", "label": "Less accumulated depreciation"},
    "box10a":{"line": "10a","label": "Depletable assets"},
    "box10b":{"line": "10b","label": "Less accumulated depletion"},
    "box11": {"line": "11", "label": "Land (net of any amortization)"},
    "box12a":{"line": "12a","label": "Intangible assets (amortizable only)"},
    "box12b":{"line": "12b","label": "Less accumulated amortization"},
    "box13": {"line": "13", "label": "Other assets (attach statement)"},
    "box14": {"line": "14", "label": "Total assets"},
    "box15": {"line": "15", "label": "Accounts payable"},
    "box16": {"line": "16", "label": "Mortgages, notes, bonds payable in less than 1 year"},
    "box17": {"line": "17", "label": "Other current liabilities (attach statement)"},
    "box18": {"line": "18", "label": "All nonrecourse loans"},
    "box19a":{"line": "19a","label": "Loans from partners (or persons related to partners)"},
    "box19b":{"line": "19b","label": "Mortgages, notes, bonds payable in 1 year or more"},
    "box20": {"line": "20", "label": "Other liabilities (attach statement)"},
    "box21": {"line": "21", "label": "Partners' capital accounts"},
    "box22": {"line": "22", "label": "Total liabilities and capital"},
}

BOX_TO_1065_SCHEDULE_M1_LINE = {
    "box1": {"line": "1","label": "Net income (loss) per books", },
    "box2": {"line": "2","label": "Income included on Schedule K, lines 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, and 11, not recorded on books this year (itemize):",},
    "box3": {"line": "3","label": "Guaranteed payments (other than health insurance)",},
    "box4": {"line": "4","label": "Expenses recorded on books this year not included on Schedule K, lines 1 through 13e, and 21 (itemize):",},
    "box5": {"line": "5","label": "Add lines 1 through 4",},
    "box6": {"line": "6","label": "Income recorded on books this year not included on Schedule K, lines 1 through 11 (itemize):",},
    "box7": {"line": "7","label": "Deductions included on Schedule K, lines 1 through 13e, and 21, not charged against book income this year (itemize):",},
    "box8": {"line": "8","label": "Add lines 6 and 7",},
    "box9": {"line": "9","label": "Income (loss) (Analysis of Net Income (Loss) per Return, line 1). Subtract line 8 from line 5.",},
}

BOX_TO_1065_SCHEDULE_M2_LINE = {
    "box1": {"line": "1","label": "Balance at beginning of year",},
    "box2a": {"line": "2a","label": "Capital contributed — Cash",},
    "box2b": {"line": "2b","label": "Capital contributed — Property",},
    "box3": {"line": "3","label": "Net income (loss)",},
    "box4": {"line": "4","label": "Other increases (itemize)",},
    "box5": {"line": "5","label": "Add lines 1 through 4",},
    "box6a": {"line": "6a","label": "Distributions — Cash",},
    "box6b": {"line": "6b","label": "Distributions — Property",},
    "box7": {"line": "7","label": "Other decreases (itemize)",},
    "box8": {"line": "8","label": "Add lines 6 and 7",},
    "box9": {"line": "9","label": "Balance at end of year. Subtract line 8 from line 5",},
}

BOX_TO_1040_LINE = {
    "Box1a": {"line": "1a", "label": "Total amount from Form(s) W-2, box 1 (see instructions)"},
    "Box1b": {"line": "1b", "label": "Household employee wages not reported on Form(s) W-2"},
    "Box1c": {"line": "1c", "label": "Tip income not reported on line 1a (see instructions)"},
    "Box1d": {"line": "1d", "label": "Medicaid waiver payments not reported on Form(s) W-2 (see instructions)"},
    "Box1e": {"line": "1e", "label": "Taxable dependent care benefits from Form 2441, line 26"},
    "Box1f": {"line": "1f", "label": "Employer-provided adoption benefits from Form 8839, line 29"},
    "Box1g": {"line": "1g", "label": "Wages from Form 8919, line 6"},
    "Box1h": {"line": "1h", "label": "Other earned income (see instructions)"},
    "Box1i": {"line": "1i", "label": "Nontaxable combat pay election (see instructions)"},
    "Box1z": {"line": "1z", "label": "Add lines 1a through 1h"},
    "Box2a": {"line": "2a", "label": "Tax-exempt interest"},
    "Box2b": {"line": "2b", "label": "Taxable interest"},
    "Box3a": {"line": "3a", "label": "Qualified dividends"},
    "Box3b": {"line": "3b", "label": "Ordinary dividends"},
    "Box4a": {"line": "4a", "label": "IRA distributions"},
    "Box4b": {"line": "4b", "label": "Taxable amount"},
    "Box5a": {"line": "5a", "label": "Pensions and annuities"},
    "Box5b": {"line": "5b", "label": "Taxable amount"},
    "Box6a": {"line": "6a", "label": "Social security benefits"},
    "Box6b": {"line": "6b", "label": "Taxable amount"},
    "Box6c": {"line": "6c", "label": "If you elect to use the lump-sum election method, check here (see instructions)"},
    "Box7": {"line": "7", "label": "Capital gain or (loss). Attach Schedule D if required. If not required, check here"},
    "Box8": {"line": "8", "label": "Additional income from Schedule 1, line 10"},
    "Box9": {"line": "9", "label": "Add lines 1z, 2b, 3b, 4b, 5b, 6b, 7, and 8. This is your total income"},
    "Box10": {"line": "10", "label": "Adjustments to income from Schedule 1, line 26"},
    "Box11": {"line": "11", "label": "Subtract line 10 from line 9. This is your adjusted gross income"},
    "Box12": {"line": "12", "label": "Standard deduction or itemized deductions (from Schedule A)"},
    "Box13": {"line": "13", "label": "Qualified business income deduction from Form 8995 or Form 8995-A"},
    "Box14": {"line": "14", "label": "Add lines 12 and 13"},
    "Box15": {"line": "15", "label": "Subtract line 14 from line 11. If zero or less, enter -0-. This is your taxable income"},
    "Box16": {"line": "16", "label": "Tax 1 see instructions. Check if an from Forms: (see instructions). Check if any from Form(s):"},
    "Box17": {"line": "17", "label": "Amount from Schedule 2, line 3"},
    "Box18": {"line": "18", "label": "Add lines 16 and 17"},
    "Box19": {"line": "19", "label": "Child tax credit or credit for other dependents from Schedule 8812"},
    "Box20": {"line": "20", "label": "Amount from Schedule 3, line 8"},
    "Box21": {"line": "21", "label": "Add lines 19 and 20"},
    "Box22": {"line": "22", "label": "Subtract line 21 from line 18. If zero or less, enter -0-"},
    "Box23": {"line": "23", "label": "Other taxes, including self-employment tax, from Schedule 2, line 21"},
    "Box24": {"line": "24", "label": "Add lines 22 and 23. This is your total tax"},
    "Box25a": {"line": "25a", "label": "Form(s) W-2"},
    "Box25b": {"line": "25b", "label": "Form(s) 1099"},
    "Box25c": {"line": "25c", "label": "Other forms (see instructions)"},
    "Box25d": {"line": "25d", "label": "Add lines 25a through 25c"},
    "Box26": {"line": "26", "label": "2024 estimated tax payments and amount applied from 2023 return"},
    "Box27": {"line": "27", "label": "Earned income credit (EIC)"},
    "Box28": {"line": "28", "label": "Additional child tax credit from Schedule 8812"},
    "Box29": {"line": "29", "label": "American opportunity credit from Form 8863, line 8"},
    "Box30": {"line": "30", "label": "Reserved for future use"},
    "Box31": {"line": "31", "label": "Amount from Schedule 3, line 15"},
    "Box32": {"line": "32", "label": "Add lines 27, 28, 29, and 31. These are your total other payments and refundable credits"},
    "Box33": {"line": "33", "label": "Add lines 25d, 26, and 32. These are your total payments"},
    "Box34": {"line": "34", "label": "If line 33 is more than line 24, subtract line 24 from line 33. This is the amount you overpaid"},
    "Box35a": {"line": "35a", "label": "Amount of line 34 you want refunded to you. If Form 8888 is attached, check here"},
    "Box36": {"line": "36", "label": "Amount of line 34 you want applied to your 2025 estimated tax"},
    "Box37": {"line": "37", "label": "Subtract line 33 from line 24. This is the amount you owe."},
    "Box38": {"line": "38", "label": "Estimated tax penalty (see instructions)"},
}

BOX_TO_1099DIV_FIELD = {
    "Box1a": {"line": "1a", "label": "Total ordinary dividends", "field": "Box1a"},
    "Box1b": {"line": "1b", "label": "Qualified dividends", "field": "Box1b"},
    "Box2a": {"line": "2a", "label": "Total capital gain distr.", "field": "Box2a"},
    "Box2b": {"line": "2b", "label": "Unrecap. Sec. 1250 gain", "field": "Box2b"},
    "Box2c": {"line": "2c", "label": "Section 1202 gain", "field": "Box2c"},
    "Box2d": {"line": "2d", "label": "Collectibles (28%) gain", "field": "Box2d"},
    "Box2e": {"line": "2e", "label": "Section 897 ordinary dividends", "field": "Box2e"},
    "Box2f": {"line": "2f", "label": "Section 897 capital gain", "field": "Box2f"},
    "Box3": {"line": "3", "label": "Nondividend distributions", "field": "Box3"},
    "Box4": {"line": "4", "label": "Federal income tax withheld", "field": "Box4"},
    "Box5": {"line": "5", "label": "Section 199A dividends", "field": "Box5"},
    "Box6": {"line": "6", "label": "Investment expenses", "field": "Box6"},
    "Box7": {"line": "7", "label": "Foreign tax paid", "field": "Box7"},
    "Box8": {"line": "8", "label": "Foreign country or U.S. possession", "field": "Box8"},
    "Box9": {"line": "9", "label": "Cash liquidation distributions", "field": "Box9"},
    "Box10": {"line": "10", "label": "Noncash liquidation distributions", "field": "Box10"},
    "Box12": {"line": "12", "label": "Exempt-interest dividends", "field": "Box12"},
    "Box13": {"line": "13", "label": "Specified private activity bond interest dividends", "field": "Box13"},
    "PayerTIN": {"line": "", "label": "Payer's TIN"},
    "PayerName": {"line": "", "label": "Payer's name"},
    "RecipientTIN": {"line": "", "label": "Recipient's TIN"},
    "RecipientName": {"line": "", "label": "Recipient's name"},
    "RecipientAccountNumber": {"line": "", "label": "Account number"},
    "PayerAddress": {"line": "", "label": "Payer's address"},
    "PayerPhoneNumber": {"line": "", "label": "Payer's phone number"},
    "RecipientAddress": {"line": "", "label": "Recipient's address"},
    "TaxYear": {"line": "", "label": "For calendar year"},
}

BOX_TO_1099INT_FIELD = {

    "Box1": {"line": "1", "label": "Interest income", "field": "Box1"},
    "Box2": {"line": "2", "label": "Early withdrawal penalty", "field": "Box2"},
    "Box3": {"line": "3", "label": "Interest on U.S. Savings Bonds and Treasury obligations", "field": "Box3"},
    "Box4": {"line": "4", "label": "Federal income tax withheld", "field": "Box4"},
    "Box5": {"line": "5", "label": "Investment expenses", "field": "Box5"},
    "Box6": {"line": "6", "label": "Foreign tax paid", "field": "Box6"},
    "Box7": {"line": "7", "label": "Foreign country or U.S. territory", "field": "Box7"},
    "Box8": {"line": "8", "label": "Tax-exempt interest", "field": "Box8"},
    "Box9": {"line": "9", "label": "Specified private activity bond interest", "field": "Box9"},
    "Box10": {"line": "10", "label": "Market discount", "field": "Box10"},
    "Box11": {"line": "11", "label": "Bond premium", "field": "Box11"},
    "Box12": {"line": "12", "label": "Bond premium on Treasury obligations", "field": "Box12"},
    "Box13": {"line": "13", "label": "Bond premium on tax-exempt bond", "field": "Box13"},
    "Box14": {"line": "14", "label": "Tax-exempt and tax credit bond CUSIP no.", "field": "Box14"},
    "TaxYear": {"line": "", "label": "For calendar year"},
    "PayerTIN": {"line": "", "label": "Payer's TIN"},
    "PayerName": {"line": "", "label": "Payer's name"},
    "RecipientTIN": {"line": "", "label": "Recipient's TIN"},
    "RecipientName": {"line": "", "label": "Recipient's name"},
    "RecipientAccountNumber": {"line": "", "label": "Account number"},
    "PayerAddress": {"line": "", "label": "Payer's address"},
    "PayerPhoneNumber": {"line": "", "label": "Payer's phone number"},
    "RecipientAddress": {"line": "", "label": "Recipient's address"},

}

BOX_TO_1099MISC_FIELD = {
    "Box1": {"line": "1", "label": "Rents", "field": "Box1"},
    "Box2": {"line": "2", "label": "Royalties", "field": "Box2"},
    "Box3": {"line": "3", "label": "Other income", "field": "Box3"},
    "Box4": {"line": "4", "label": "Federal income tax withheld", "field": "Box4"},
    "Box5": {"line": "5", "label": "Fishing boat proceeds", "field": "Box5"},
    "Box6": {"line": "6", "label": "Medical and health care payments", "field": "Box6"},
    "Box8": {"line": "8", "label": "Substitute payments in lieu of dividends or interest", "field": "Box8"},
    "Box9": {"line": "9", "label": "Crop insurance proceeds", "field": "Box9"},
    "Box10": {"line": "10", "label": "Gross proceeds paid to an attorney", "field": "Box10"},
    "Box11": {"line": "11", "label": "Fish purchased for resale", "field": "Box11"},
    "Box12": {"line": "12", "label": "Section 409A deferrals", "field": "Box12"},
    "Box15": {"line": "15", "label": "Nonqualified deferred compensation", "field": "Box15"},
    "TaxYear": {"line": "", "label": "For calendar year"},
    "PayerTIN": {"line": "", "label": "Payer's TIN"},
    "PayerName": {"line": "", "label": "Payer's name"},
    "PayerAddress": {"line": "", "label": "Payer's address"},
    "PayerPhoneNumber": {"line": "", "label": "Payer's phone number"},
    "RecipientTIN": {"line": "", "label": "Recipient's TIN"},
    "RecipientName": {"line": "", "label": "Recipient's name"},
    "RecipientAddress": {"line": "", "label": "Recipient's address"},
    "RecipientAccountNumber": {"line": "", "label": "Account number"},
}

BOX_TO_1099NEC_FIELD = {
    "Box1": {"line": "1", "label": "Nonemployee compensation"},
    "Box2": {"line": "2", "label": "Payer made direct sales totaling $5,000 or more of consumer products to recipient for resale"},
    "Box3": {"line": "3", "label": "Other income"},
    "Box4": {"line": "4", "label": "Excess golden parachute payments"},
    "PayerTIN": {"line": "", "label": "Payer's TIN"},
    "PayerName": {"line": "", "label": "Payer's name"},
    "PayerAddress": {"line": "", "label": "Payer's address"},
    "RecipientTIN": {"line": "", "label": "Recipient's TIN"},
    "RecipientName": {"line": "", "label": "Recipient's name"},
    "RecipientAddress": {"line": "", "label": "Recipient's address"},
}
BOX_TO_W2_FIELD = {
    "box1": {"line": "1", "label": "Wages, tips, other compensation"},
    "box2": {"line": "2", "label": "Federal income tax withheld"},
    "box3": {"line": "3", "label": "Social security wages"},
    "box4": {"line": "4", "label": "Social security tax withheld"},
    "box5": {"line": "5", "label": "Medicare wages and tips"},
    "box6": {"line": "6", "label": "Medicare tax withheld"},
    "box7": {"line": "7", "label": "Social security tips"},
    "box8": {"line": "8", "label": "Allocated tips"},
    "box10": {"line": "10", "label": "Dependent care benefits"},
    "box11": {"line": "11", "label": "Nonqualified plans"},
    "box14": {"line": "14", "label": "Other"},
    "TaxYear": {"line": "", "label": "Tax Year"},
    "W2FormVariant": {"line": "", "label": "Form"},
    "ControlNumber": {"line": "d", "label": "Control Number"},
    "SSN": {"line": "a", "label": "Employee's social security number"},
    "EIN": {"line": "b", "label": "Employer identification number (EIN)"},
}
# BOX_TO_W2_2_FIELD = {
#     "ControlNumber": {"line": "", "label": "Control Number", "field": "ControlNumber"},
#     "Box2": {"line": "2", "label": "Federal income tax withheld", "field": "FederalIncomeTaxWithheld"},
#     "Box3": {"line": "3", "label": "Social security wages", "field": "SocialSecurityWages"},
#     "Box4": {"line": "4", "label": "Social security tax withheld", "field": "SocialSecurityTaxWithheld"},
#     "Box5": {"line": "5", "label": "Medicare wages and tips", "field": "MedicareWagesAndTips"},
#     "Box6": {"line": "6", "label": "Medicare tax withheld", "field": "MedicareTaxWithheld"},
# }

# BOX_TO_W2_FIELD = {
#     "Box1": {"line": "1", "label": "Wages, tips, other compensation", "field": "Box1"},
#     "Box2": {"line": "2", "label": "Federal income tax withheld", "field": "Box2"},
#     "Box3": {"line": "3", "label": "Social security wages", "field": "Box3"},
#     "Box4": {"line": "4", "label": "Social security tax withheld", "field": "Box4"},
#     "Box5": {"line": "5", "label": "Medicare wages and tips", "field": "Box5"},
#     "Box6": {"line": "6", "label": "Medicare tax withheld", "field": "Box6"},
#     "Box7": {"line": "7", "label": "Social security tips", "field": "Box7"},
#     "Box8": {"line": "8", "label": "Allocated tips", "field": "Box8"},
#     "Box10": {"line": "10", "label": "Dependent care benefits", "field": "Box10"},
#     "Box11": {"line": "11", "label": "Nonqualified plans", "field": "Box11"},
#     "Box14": {"line": "14", "label": "Other", "field": "Box14"},
# }


BOX_TO_W2G_FIELD = {
    "Box1": {"line": "1", "label": "Wages, tips, other compensation", "field": "WagesTipsAndOtherCompensation"},
    "Box2": {"line": "2", "label": "Federal income tax withheld", "field": "FederalIncomeTaxWithheld"},
    "Box3": {"line": "3", "label": "Social security wages", "field": "SocialSecurityWages"},
    "Box4": {"line": "4", "label": "Social security tax withheld", "field": "SocialSecurityTaxWithheld"},
    "Box5": {"line": "5", "label": "Medicare wages and tips", "field": "MedicareWagesAndTips"},
}
BOX_TO_1099SSA_FIELD = {
    "Address": {"line": "7", "label": "Address"},
    "Name": {"line": "1", "label": "Name"},
    "SSN": {"line": "2", "label": "Beneficiary's Social security number"},
    "Box3": {"line": "3", "label": "Benefits Paid"},
    "Box4": {"line": "4", "label": "Benefits Repaid to SSA"},
    "Box5": {"line": "5", "label": "Net Benefits"},
    "Box6": {"line": "6", "label": "Voluntary Federal Income Tax Withholding"},
    "ClaimNumber": {"line": "8", "label": "Claim Number"},
    "TaxYear": {"line": "", "label": "Tax Year"},
}
BOX_TO_1099R_FIELD = {
    "Box1": {"line": "1", "label": "Gross distribution"},
    "Box2a": {"line": "2a", "label": "Taxable amount"},
    "Box2b": {"line": "2b", "label": "Taxable amount not determined"},
    "Box3": {"line": "3", "label": "Capital gain (included in box 2a)"},
    "Box4": {"line": "4", "label": "Federal income tax withheld"},
    "Box5": {"line": "5", "label": "Employee contributions/Designated Roth contributions or insurance premiums"},
    "Box6": {"line": "6", "label": "Net unrealized appreciation in employer's securities"},
    "Box7": {"line": "7", "label": "Distribution code(s)"},
    "IsIraSepSimple": {"line": "8", "label": "IRA/SEP/SIMPLE"},
    "Box8Percentage": {"line": "8", "label": "Other"},
    "Box9a": {"line": "9a", "label": "Your percentage of total distribution"},
    "Box9b": {"line": "9b", "label": "Total employee contributions"},
    "Box11": {"line": "11", "label": "1st year of desig. Roth contrib."},
    "Box12": {"line": "12", "label": "FATCA filing requirement"},
    "Box13": {"line": "13", "label": "Date of payment"},
    "TaxYear": {"line": "", "label": "Tax Year"},
    "PayerTIN": {"line": "", "label": "Payer's TIN"},
    "PayerName": {"line": "", "label": "Payer's name"},
    "PayerAddress": {"line": "", "label": "Payer's address"},
    "RecipientTIN": {"line": "", "label": "Recipient's TIN"},
    "RecipientName": {"line": "", "label": "Recipient's name"},
    "RecipientAddress": {"line": "", "label": "Recipient's address"},
    "RecipientAccountNumber": {"line": "", "label": "Account number"},
}
# Map model IDs to their corresponding field mappings
MODEL_TO_MAPPING: Dict[str, Dict[str, Dict[str, str]]] = {
    "Train_1120s_v2": FORM_1120S,
    "Train_1120s_schedule_L_v4": Form_1120s_SCHEDULE_L_LINE,
    "Train_1120s_scehdule_M1_v2": Form_1120s_SCHEDULE_M1_LINE,
    "Train_1120s_schedule_M2_v3": Form_1120s_SCHEDULE_M2_LINE,
    "Train_1120_v2": BOX_TO_1120_LINE,
    "Train_1120_schedule_L_v3": BOX_TO_1120_SCHEDULE_L_LINE,
    "Train_1120_schedule_M2_v3": BOX_TO_1120_SCHEDULE_M2_LINE,
    "Train_1120_schedule_M1_v2": BOX_TO_1120_SCHEDULE_M1_LINE,
    "Train_model_1065_v4": BOX_TO_1065_LINE,
    "Train_1065_schedule_L_v4": BOX_TO_1065_SCHEDULE_L_LINE,
    "Train_1065_schedule_m2_v3": BOX_TO_1065_SCHEDULE_M2_LINE,
    "Train_1065_schedule_m1_v2": BOX_TO_1065_SCHEDULE_M1_LINE,
    "prebuilt-tax.us.1040": BOX_TO_1040_LINE,
    "prebuilt-tax.us.1099DIV": BOX_TO_1099DIV_FIELD,
    "prebuilt-tax.us.1099INT": BOX_TO_1099INT_FIELD,
    "prebuilt-tax.us.1099MISC": BOX_TO_1099MISC_FIELD,
    "prebuilt-tax.us.1099NEC": BOX_TO_1099NEC_FIELD,
    "prebuilt-tax.us.1099R": BOX_TO_1099R_FIELD,
    "Train_model_w2_v4": BOX_TO_W2_FIELD,
    "model_w2g_v1": BOX_TO_W2G_FIELD,
    "prebuilt-tax.us.1099SSA": BOX_TO_1099SSA_FIELD,
}

def get_mapping_for_model(model_id: str) -> Optional[Dict[str, Dict[str, str]]]:
    """
    Get the field mapping dictionary for a given model ID.
    
    :param model_id: The Azure model ID (e.g., "Train_1120s_v2")
    :return: Mapping dictionary or None if no mapping exists
    """
    return MODEL_TO_MAPPING.get(model_id)


def process_w2_box12(box12_data: list) -> Dict[str, Dict[str, Any]]:
    """
    Process Box12 array data into separate Code and Amount entries.
    
    :param box12_data: List of dictionaries with 'LetterCode' and 'Amount' keys
    :return: Dictionary with box12 entries (box12a, box12a_amount, box12b, etc.)
    """
    box12_mapped = {}
    letters = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z']
    
    for idx, item in enumerate(box12_data):
        if idx >= len(letters):
            break  # Limit to 26 entries (a-z)
        
        letter = letters[idx]
        line_num = f"12{letter}"
        
        # Extract LetterCode and Amount
        letter_code = item.get('LetterCode', '')
        amount = _format_two_decimal(item.get('Amount', None))
        
        # Add Code entry
        box12_mapped[f"box12{letter}"] = {
            "line": line_num,
            "label": "Code",
            "value": letter_code
        }
        
        # Add Amount entry
        box12_mapped[f"box12{letter}_amount"] = {
            "line": line_num,
            "label": "Amount",
            "value": amount
        }
    
    return box12_mapped


def transform_state_local_table(tax_infos: list) -> Dict[str, Any]:
    """
    Transform state/local taxes table to support duplicate states by assigning unique keys
    (e.g., OH_1, OH_2) while keeping display labels as the base state (e.g., OH, OH).
    """
    if not isinstance(tax_infos, list) or len(tax_infos) == 0:
        return {}
    
    field_to_line_label = {
        'EmployerStateIdNumber': {'line': '15', 'label': "Employer's state ID number"},
        'box16': {'line': '16', 'label': 'State wages, tips, etc.'},
        'box17': {'line': '17', 'label': 'State income tax'},
        'box18': {'line': '18', 'label': 'Local wages, tips, etc.'},
        'box19': {'line': '19', 'label': 'Local income tax'},
        'box20': {'line': '20', 'label': 'Name of locality'},
    }
    
    state_counts: Dict[str, int] = {}
    for tax_info in tax_infos:
        if isinstance(tax_info, dict):
            state = tax_info.get("State")
            if state:
                state_counts[state] = state_counts.get(state, 0) + 1
    
    state_aliases: List[str] = []
    state_labels: List[str] = []
    valid_tax_infos: List[Dict[str, Any]] = []
    
    for tax_info in tax_infos:
        if not isinstance(tax_info, dict):
            continue
        state = tax_info.get('State')
        if not state:
            continue
        # Use bare state if it appears once; otherwise suffix
        if state_counts.get(state, 0) == 1:
            alias = state
        else:
            count_so_far = state_labels.count(state) + 1
            alias = f"{state}_{count_so_far}"
        state_aliases.append(alias)
        state_labels.append(state)
        valid_tax_infos.append(tax_info)
    
    if not state_aliases:
        return {}
    
    rows = []
    for field_name, line_label in field_to_line_label.items():
        row_dict = {
            'line': line_label['line'],
            'label': line_label['label']
        }
        for idx, tax_info in enumerate(valid_tax_infos):
            alias = state_aliases[idx]
            value = tax_info.get(field_name, '')
            if field_name in STATE_LOCAL_NUMERIC_FIELDS:
                value = _format_two_decimal(value)
            row_dict[alias] = value
        rows.append(row_dict)
    
    return {
        'rows': rows,
        'states': state_aliases,      # keys used in data (unique)
        'state_labels': state_labels  # display labels (can repeat)
    }


def transform_1099div_state_taxes(state_taxes: list) -> Dict[str, Any]:
    """
    Transform 1099-DIV StateTaxesWithheld array into a simple table structure.
    Expected items: {'Box14': state, 'Box15': state identification no., 'Box16': state tax withheld}
    Returns rows list and fields list for predictable rendering/export.
    """
    if not isinstance(state_taxes, list) or len(state_taxes) == 0:
        return {}
    
    fields = ["Box14", "Box15", "Box16"]
    rows = []
    for entry in state_taxes:
        if not isinstance(entry, dict):
            continue
        row = {
            "State": entry.get("Box14", ""),
            "StateIdentificationNumber": entry.get("Box15", ""),
            "StateTaxWithheld": _format_two_decimal(entry.get("Box16", "")),
        }
        rows.append(row)
    
    if not rows:
        return {}
    
    return {
        "rows": rows,
        "fields": ["State", "StateIdentificationNumber", "StateTaxWithheld"]
    }


def transform_1099int_state_taxes(state_taxes: list) -> Dict[str, Any]:
    """
    Transform 1099-INT StateTaxesWithheld array into a simple table structure.
    Expected items: {'Box15': state, 'Box16': state identification no., 'Box17': state tax withheld}
    Returns rows list and fields list for predictable rendering/export.
    Note: Box17 is formatted to 2 decimals.
    """
    if not isinstance(state_taxes, list) or len(state_taxes) == 0:
        return {}
    
    fields = ["Box15", "Box16", "Box17"]
    rows = []
    for entry in state_taxes:
        if not isinstance(entry, dict):
            continue
        # Box17 is formatted to 2 decimals
        box17_value = _format_two_decimal(entry.get("Box17", ""))
        row = {
            "State": entry.get("Box15", ""),
            "StateIdentificationNumber": entry.get("Box16", ""),
            "StateTaxWithheld": box17_value,
        }
        rows.append(row)
    
    if not rows:
        return {}
    
    return {
        "rows": rows,
        "fields": ["State", "StateIdentificationNumber", "StateTaxWithheld"]
    }


def transform_1099misc_state_taxes(state_taxes: list) -> Dict[str, Any]:
    """
    Transform 1099-MISC StateTaxesWithheld array into a simple table structure.
    Expected items: {'Box16': state tax withheld, 'Box17': state/payer's state no., 'Box18': state income}
    Returns rows list and fields list for predictable rendering/export.
    Note: Box16 and Box18 are formatted to 2 decimals.
    """
    if not isinstance(state_taxes, list) or len(state_taxes) == 0:
        return {}
    
    fields = ["Box16", "Box17", "Box18"]
    rows = []
    for entry in state_taxes:
        if not isinstance(entry, dict):
            continue
        # Box16 (State tax withheld) and Box18 (State income) are formatted to 2 decimals
        # Box17 (State/Payer's state no.) is kept as string
        row = {
            "StateTaxWithheld": _format_two_decimal(entry.get("Box16", "")),
            "StateIdentificationNumber": entry.get("Box17", ""),
            "StateIncome": _format_two_decimal(entry.get("Box18", "")),
        }
        rows.append(row)
    
    if not rows:
        return {}
    
    return {
        "rows": rows,
        "fields": ["StateTaxWithheld", "StateIdentificationNumber", "StateIncome"]
    }


def transform_1099nec_state_taxes(state_taxes: list) -> Dict[str, Any]:
    """
    Transform 1099-NEC StateTaxesWithheld array into a simple table structure.
    Expected items: {'Box5': state tax withheld, 'Box6': state/payer's state no., 'Box7': state income}
    Returns rows list and fields list for predictable rendering/export.
    """
    if not isinstance(state_taxes, list) or len(state_taxes) == 0:
        return {}
    
    fields = ["Box5", "Box6", "Box7"]
    rows = []
    for entry in state_taxes:
        if not isinstance(entry, dict):
            continue
        row = {
            "StateTaxWithheld": _format_two_decimal(entry.get("Box5", "")),
            "StateIdentificationNumber": entry.get("Box6", ""),
            "StateIncome": _format_two_decimal(entry.get("Box7", "")),
        }
        rows.append(row)
    
    if not rows:
        return {}
    
    return {
        "rows": rows,
        "fields": ["StateTaxWithheld", "StateIdentificationNumber", "StateIncome"]
    }


def transform_1099r_state_taxes(state_taxes: list) -> Dict[str, Any]:
    """
    Transform 1099-R StateTaxesWithheld array into a simple table structure.
    Expected items: {'Box14': state tax withheld, 'Box15': state/payer's state no., 'Box16': state distribution}
    Returns rows list and fields list for predictable rendering/export.
    Note: Box14 may contain $ symbols that need cleanup.
    """
    if not isinstance(state_taxes, list) or len(state_taxes) == 0:
        return {}
    
    rows = []
    for entry in state_taxes:
        if not isinstance(entry, dict):
            continue
        # Box14 might have $ symbol, need to clean it
        box14_value = entry.get("Box14", "")
        if isinstance(box14_value, str):
            box14_value = box14_value.replace("$", "").replace(",", "").strip()
        row = {
            "StateTaxWithheld": _format_two_decimal(box14_value),
            "StateIdentificationNumber": entry.get("Box15", ""),
            "StateDistribution": _format_two_decimal(entry.get("Box16", "")),
        }
        rows.append(row)
    
    if not rows:
        return {}
    
    return {
        "rows": rows,
        "fields": ["StateTaxWithheld", "StateIdentificationNumber", "StateDistribution"]
    }


def transform_1099r_local_taxes(local_taxes: list) -> Dict[str, Any]:
    """
    Transform 1099-R LocalTaxesWithheld array into a simple table structure.
    Expected items: {'Box17': local tax withheld, 'Box18': name of locality, 'Box19': local distribution}
    Returns rows list and fields list for predictable rendering/export.
    Note: Box17 may contain $ symbols that need cleanup.
    """
    if not isinstance(local_taxes, list) or len(local_taxes) == 0:
        return {}
    
    rows = []
    for entry in local_taxes:
        if not isinstance(entry, dict):
            continue
        # Box17 might have $ symbol, need to clean it
        box17_value = entry.get("Box17", "")
        if isinstance(box17_value, str):
            box17_value = box17_value.replace("$", "").replace(",", "").strip()
        row = {
            "LocalTaxWithheld": _format_two_decimal(box17_value),
            "LocalityName": entry.get("Box18", ""),
            "LocalDistribution": _format_two_decimal(entry.get("Box19", "")),
        }
        rows.append(row)
    
    if not rows:
        return {}
    
    return {
        "rows": rows,
        "fields": ["LocalTaxWithheld", "LocalityName", "LocalDistribution"]
    }


def _resolve_box_value(box_name: str, fields: Dict[str, Any]) -> Any:
    """
    Resolve box value from fields dictionary using box-c and box-d variants.
    Priority: box-c > box-d > box-c (as fallback).
    
    For simple boxes (box1, box3): checks box1c, box1d
    For complex boxes (box2a, box7a): checks box2a-c, box2a-d
    
    :param box_name: Base box name (e.g., "box1", "box2a")
    :param fields: Dictionary of field names to values
    :return: Resolved value (may be None)
    """
    # Remove "box" prefix to get the base identifier (e.g., "1", "2a", "10a")
    base = box_name[3:] if box_name.startswith("box") else box_name
    
    # Determine if box is complex (ends with a single letter after digits)
    # Examples: "2a", "7a", "10a" are complex; "1", "3", "22" are simple
    is_complex = len(base) > 1 and base[-1].isalpha() and base[:-1].isdigit()
    
    if is_complex:
        # Complex boxes use dash format: box2a-c, box2a-d
        box_c_key = f"box{base}-c"
        box_d_key = f"box{base}-d"
    else:
        # Simple boxes use direct suffix: box1c, box1d
        box_c_key = f"box{base}c"
        box_d_key = f"box{base}d"
    
    # Priority logic:
    # 1. If box-c exists and is not None/null → return that value
    # 2. Else if box-d exists and is not None/null → return that value
    # 3. Else → return box-c value (may be None)
    box_c_value = fields.get(box_c_key)
    box_d_value = fields.get(box_d_key)
    
    if box_c_value not in (None, ""):
        return box_c_value
    elif box_d_value not in (None, ""):
        return box_d_value
    else:
        # Fallback: use box-c value even if None
        return box_c_value
    
def normalize_value(text: str):
    text = text.strip()

    if text == "()":
        return None

    match_paren = re.search(r'\(\s*(\d{1,3}(?:,\s*\d{3})*(?:\.\d+)?)', text)
    if match_paren:
        value = match_paren.group(1)
        value = re.sub(r',\s+', ',', value)
        return f"({value})"

    match = re.search(r'\d{1,3}(?:,\s*\d{3})*(?:\.\d+)?', text)
    if not match:
        return None

    value = match.group(0)
    value = re.sub(r',\s+', ',', value)

    if ")" in text:
        return f"({value})"

    return value


def map_fields_to_line_label_value(
    fields: Dict[str, Any],
    model_id: str
) -> Dict[str, Dict[str, Any]]:
    """
    Transform fields dictionary to include Line, Label, and Value structure.
    Only includes fields that have a mapping - unmapped fields are excluded.
    
    For Schedule L mappings (BOX_TO_1065_SCHEDULE_L_LINE, BOX_TO_1120_SCHEDULE_L_LINE, 
    Form_1120s_SCHEDULE_L_LINE), uses special logic to resolve box-c and box-d variants 
    with priority: box-c > box-d > box-c (fallback).
    
    :param fields: Dictionary of field names to values from analyze_pdf_with_model
    :param model_id: The Azure model ID to determine which mapping to use
    :return: Dictionary with mapped fields containing Line, Label, and Value
    """
    mapping = get_mapping_for_model(model_id)
    
    if not mapping:
        # If no mapping exists, return empty dict (only return values that have mappings)
        return {}
    
    # Check if this is a Schedule L mapping that requires special handling (box-c/box-d variant resolution)
    is_schedule_l_with_variants = (
        model_id == "Train_1065_schedule_L_v4" or 
        model_id == "Train_1120_schedule_L_v3" or
        model_id == "Train_1120s_schedule_L_v4" or
        mapping is BOX_TO_1065_SCHEDULE_L_LINE or
        mapping is BOX_TO_1120_SCHEDULE_L_LINE or
        mapping is Form_1120s_SCHEDULE_L_LINE 
    )
    
    mapped_fields = {}
    
    if is_schedule_l_with_variants:
        # For Schedule L mappings, iterate through mapping keys and resolve box-c/box-d variants
        for box_name in mapping.keys():
            value = _resolve_box_value(box_name, fields)
            # Include the mapping even if value is None (as per fallback logic)
            mapped_fields[box_name] = {
                "line": mapping[box_name]["line"],
                "label": mapping[box_name]["label"],
                "value": normalize_value(value) if value is not None else None
            }
    else:
        # Check if this is a W2 form (new simplified logic)
        is_w2_form = (
            model_id == "Train_model_w2_v4"
        )
        
        if is_w2_form:
            # For W2 forms, map basic boxes based on mapping definition to preserve order
            for field_name, map_item in mapping.items():
                if field_name in fields:
                    value = fields[field_name]
                    if field_name in W2_NUMERIC_FIELDS:
                        value = _format_two_decimal(value)
                    mapped_fields[field_name] = {
                        "line": map_item["line"],
                        "label": map_item["label"],
                        "value": value
                    }
        else:
            # Check if this is a 1099 or W2G form with Transactions array
            is_1099_or_w2g_form = (
                model_id == "prebuilt-tax.us.1099INT" or
                model_id == "prebuilt-tax.us.1099DIV" or
                model_id == "prebuilt-tax.us.1099MISC" or
                model_id == "prebuilt-tax.us.1099NEC" or
                model_id == "prebuilt-tax.us.1099R" or
                model_id == "prebuilt-tax.us.1099SSA" or
                model_id == "model_w2g_v1"
            )
            
            if is_1099_or_w2g_form:
                has_transactions = "Transactions" in fields and isinstance(fields.get("Transactions"), list)
                if has_transactions:
                    # Extract Box values from Transactions array (use first transaction)
                    transactions = fields.get("Transactions", [])
                    if transactions and isinstance(transactions[0], dict):
                        transaction_fields = transactions[0]
                        # Map Box fields from the first transaction
                        for box_name in mapping.keys():
                            # Check for box name first (e.g., "Box1")
                            if box_name in transaction_fields:
                                mapped_fields[box_name] = {
                                    "line": mapping[box_name]["line"],
                                    "label": mapping[box_name]["label"],
                                    "value": transaction_fields[box_name]
                                }
                            # For W2G forms, also check field name
                            elif model_id == "model_w2g_v1" and "field" in mapping[box_name]:
                                field_name = mapping[box_name]["field"]
                                if field_name in transaction_fields:
                                    mapped_fields[box_name] = {
                                        "line": mapping[box_name]["line"],
                                        "label": mapping[box_name]["label"],
                                        "value": transaction_fields[field_name]
                                    }
                else:
                    # Fallback: map directly from top-level fields
                    for field_name, map_item in mapping.items():
                        if field_name in fields:
                            mapped_fields[field_name] = {
                                "line": map_item["line"],
                                "label": map_item["label"],
                                "value": fields[field_name]
                            }

                # Map payer/recipient identity fields (top-level)
                if model_id in {
                    "prebuilt-tax.us.1099DIV",
                    "prebuilt-tax.us.1099INT",
                    "prebuilt-tax.us.1099MISC",
                    "prebuilt-tax.us.1099NEC",
                    "prebuilt-tax.us.1099R",
                }:
                    payer = fields.get("Payer") if isinstance(fields.get("Payer"), dict) else {}
                    recipient = fields.get("Recipient") if isinstance(fields.get("Recipient"), dict) else {}
                    identity_values = {
                        "PayerTIN": payer.get("TIN", ""),
                        "PayerName": payer.get("Name", ""),
                        "PayerAddress": payer.get("Address", ""),
                        "PayerPhoneNumber": payer.get("PhoneNumber", ""),
                        "RecipientTIN": recipient.get("TIN", ""),
                        "RecipientName": recipient.get("Name", ""),
                        "RecipientAddress": recipient.get("Address", ""),
                        "RecipientAccountNumber": recipient.get("AccountNumber", ""),
                        "TaxYear": fields.get("TaxYear", ""),
                    }
                    for field_key, field_value in identity_values.items():
                        if field_key in mapping:
                            mapped_fields[field_key] = {
                                "line": mapping[field_key]["line"],
                                "label": mapping[field_key]["label"],
                                "value": field_value
                            }
                
                # Map beneficiary identity fields for 1099-SSA (nested Beneficiary object)
                if model_id == "prebuilt-tax.us.1099SSA":
                    beneficiary = fields.get("Beneficiary") if isinstance(fields.get("Beneficiary"), dict) else {}
                    identity_values = {
                        "Name": beneficiary.get("Name", ""),
                        "SSN": beneficiary.get("SSN", ""),
                        "Address": beneficiary.get("Address", ""),
                        "TaxYear": fields.get("TaxYear", ""),
                        "ClaimNumber": fields.get("ClaimNumber", ""),
                    }
                    for field_key, field_value in identity_values.items():
                        if field_key in mapping:
                            mapped_fields[field_key] = {
                                "line": mapping[field_key]["line"],
                                "label": mapping[field_key]["label"],
                                "value": field_value
                            }
            else:
                # For other mappings, iterate over mapping to preserve order
                for field_name, map_item in mapping.items():
                    if field_name in fields:
                        value = fields[field_name]
                        # Apply normalization for string values, keep others as is.
                        normalized_val = normalize_value(value) if isinstance(value, str) else value
                        mapped_fields[field_name] = {
                            "line": map_item["line"],
                            "label": map_item["label"],
                            "value": normalized_val
                        }
                    # Fields not in mapping are excluded (removed)
    
    return mapped_fields


def apply_mapping_to_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply field mapping to a result from analyze_pdf_with_model.
    Transforms the 'fields' dictionary to include Line, Label, and Value.
    For W2 forms, also processes box12 array and state/local taxes table.
    
    :param result: Result dictionary from analyze_pdf_with_model
    :return: Result dictionary with mapped fields
    """
    if not isinstance(result, dict):
        return result
    
    # Get model_id from result
    model_id = result.get("_model_id")
    if not model_id:
        return result
    # Get fields dictionary
    fields = result.get("fields", {})
    if not fields:
        return result
    
    # Check if this is a W2 form
    is_w2_form = (
        model_id == "Train_model_w2_v4"
    )
    is_1099div_form = (model_id == "prebuilt-tax.us.1099DIV")
    is_1099int_form = (model_id == "prebuilt-tax.us.1099INT")
    is_1099misc_form = (model_id == "prebuilt-tax.us.1099MISC")
    is_1099nec_form = (model_id == "prebuilt-tax.us.1099NEC")
    is_1099r_form = (model_id == "prebuilt-tax.us.1099R")
    is_1099ssa_form = (model_id == "prebuilt-tax.us.1099SSA")
    
    # Apply mapping for basic fields
    mapped_fields = map_fields_to_line_label_value(fields, model_id)
    
    # For 1099-DIV, format numeric boxes (except Box8) to 2-decimal strings
    if is_1099div_form:
        numeric_boxes = {
            "Box1a", "Box1b",
            "Box2a", "Box2b", "Box2c", "Box2d", "Box2e", "Box2f",
            "Box3",
            "Box4",
            "Box5",
            "Box6",
            "Box7",
            # skip Box8
            "Box9",
            "Box10",
            "Box12",
            "Box13",
        }
        for box_name in numeric_boxes:
            if box_name in mapped_fields:
                mapped_fields[box_name]["value"] = _format_two_decimal(mapped_fields[box_name].get("value"))
    
    # For 1099-INT, format numeric boxes to 2-decimal strings (except Box7 and Box14)
    if is_1099int_form:
        numeric_boxes = {
            "Box1", "Box2", "Box3", "Box4", "Box5", "Box6",
            # skip Box7 (Foreign country or U.S. territory)
            "Box8", "Box9", "Box10", "Box11", "Box12", "Box13",
            # skip Box14 (Tax-exempt and tax credit bond CUSIP no.)
        }
        for box_name in numeric_boxes:
            if box_name in mapped_fields:
                mapped_fields[box_name]["value"] = _format_two_decimal(mapped_fields[box_name].get("value"))
    
    # For 1099-MISC, format all numeric boxes to 2-decimal strings
    if is_1099misc_form:
        numeric_boxes = {
            "Box1", "Box2", "Box3", "Box4", "Box5", "Box6",
            "Box8", "Box9", "Box10", "Box11", "Box12", "Box15"
        }
        for box_name in numeric_boxes:
            if box_name in mapped_fields:
                mapped_fields[box_name]["value"] = _format_two_decimal(mapped_fields[box_name].get("value"))

    # For 1099-NEC, format numeric boxes to 2-decimal strings (exclude box2 flag)
    if is_1099nec_form:
        numeric_boxes = {
            "Box1",  # Nonemployee compensation
            "Box3",  # Other income
            "Box4",  # Excess golden parachute payments
        }
        for box_name in numeric_boxes:
            if box_name in mapped_fields:
                mapped_fields[box_name]["value"] = _format_two_decimal(mapped_fields[box_name].get("value"))

    # For 1099-SSA, format numeric boxes to 2-decimal strings
    if is_1099ssa_form:
        numeric_boxes = {
            "Box3",  # Benefits Paid
            "Box4",  # Benefits Repaid to SSA
            "Box5",  # Net Benefits
            "Box6",  # Voluntary Federal Income Tax Withholding
        }
        for box_name in numeric_boxes:
            if box_name in mapped_fields:
                mapped_fields[box_name]["value"] = _format_two_decimal(mapped_fields[box_name].get("value"))

    # For 1099-R, format numeric boxes to 2-decimal strings
    if is_1099r_form:
        numeric_boxes = {
            "Box1",  # Gross distribution
            "Box2a",  # Taxable amount
            "Box3",  # Capital gain
            "Box4",  # Federal income tax withheld
            "Box5",  # Employee contributions
            "Box6",  # Net unrealized appreciation
            "Box9a",  # Percentage of total distribution
            "Box9b",  # Total employee contributions
            "Box11",  # First year of designated Roth contributions
        }
        for box_name in numeric_boxes:
            if box_name in mapped_fields:
                mapped_fields[box_name]["value"] = _format_two_decimal(mapped_fields[box_name].get("value"))
    
    # Create new result with mapped fields
    mapped_result = result.copy()
    mapped_result["fields"] = mapped_fields
    
    # For W2 forms, process box12 and table if present
    if is_w2_form:
        # Process box12 array if present
        box12_data = fields.get("box12")
        if box12_data and isinstance(box12_data, list):
            box12_mapped = process_w2_box12(box12_data)
            # Add box12 entries to the result (separate from fields for Excel export)
            mapped_result["box12"] = box12_mapped
        
        # Process state/local taxes table if present
        tax_infos = fields.get("TaxInfos")
        if tax_infos and isinstance(tax_infos, list):
            state_local_taxes = transform_state_local_table(tax_infos)
            if state_local_taxes:
                mapped_result["state_local_taxes"] = state_local_taxes
    
    # For 1099-DIV, process state taxes withheld (from first transaction)
    if is_1099div_form:
        transactions = fields.get("Transactions")
        if isinstance(transactions, list) and transactions:
            first_tx = transactions[0] if isinstance(transactions[0], dict) else None
            if first_tx:
                state_taxes = first_tx.get("StateTaxesWithheld")
                state_taxes_table = transform_1099div_state_taxes(state_taxes)
                if state_taxes_table:
                    mapped_result["state_taxes_withheld"] = state_taxes_table
    
    # For 1099-INT, process state taxes withheld (from first transaction)
    if is_1099int_form:
        transactions = fields.get("Transactions")
        if isinstance(transactions, list) and transactions:
            first_tx = transactions[0] if isinstance(transactions[0], dict) else None
            if first_tx:
                state_taxes = first_tx.get("StateTaxesWithheld")
                state_taxes_table = transform_1099int_state_taxes(state_taxes)
                if state_taxes_table:
                    mapped_result["state_taxes_withheld"] = state_taxes_table
    
    # For 1099-MISC, process state taxes withheld (from first transaction or direct field)
    if is_1099misc_form:
        state_taxes_table = None
        # Prefer Transactions array if present
        transactions = fields.get("Transactions")
        if isinstance(transactions, list) and transactions:
            first_tx = transactions[0] if isinstance(transactions[0], dict) else None
            if first_tx:
                state_taxes = first_tx.get("StateTaxesWithheld")
                state_taxes_table = transform_1099misc_state_taxes(state_taxes)
        # Fallback: direct StateTaxesWithheld at top level
        if state_taxes_table is None:
            state_taxes_direct = fields.get("StateTaxesWithheld")
            state_taxes_table = transform_1099misc_state_taxes(state_taxes_direct)
        if state_taxes_table:
            mapped_result["state_taxes_withheld"] = state_taxes_table

    # For 1099-NEC, process state taxes withheld (from first transaction or direct field)
    if is_1099nec_form:
        state_taxes_table = None
        transactions = fields.get("Transactions")
        if isinstance(transactions, list) and transactions:
            first_tx = transactions[0] if isinstance(transactions[0], dict) else None
            if first_tx:
                state_taxes = first_tx.get("StateTaxesWithheld")
                state_taxes_table = transform_1099nec_state_taxes(state_taxes)
        if state_taxes_table is None:
            state_taxes_direct = fields.get("StateTaxesWithheld")
            state_taxes_table = transform_1099nec_state_taxes(state_taxes_direct)
        if state_taxes_table:
            mapped_result["state_taxes_withheld"] = state_taxes_table

    # For 1099-R, process state and local taxes withheld (top-level)
    if is_1099r_form:
        state_taxes = fields.get("StateTaxesWithheld")
        state_taxes_table = transform_1099r_state_taxes(state_taxes)
        if state_taxes_table:
            mapped_result["state_taxes_withheld"] = state_taxes_table
        
        local_taxes = fields.get("LocalTaxesWithheld")
        local_taxes_table = transform_1099r_local_taxes(local_taxes)
        if local_taxes_table:
            mapped_result["local_taxes_withheld"] = local_taxes_table
    
    return mapped_result
