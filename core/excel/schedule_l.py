"""
Excel export for Form 1120-S Schedule L
"""
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


SCHEDULE_L_LINES = [
    ("1",  "Cash"),
    ("2a", "Trade notes and accounts receivable"),
    ("2b", "Less allowance for bad debts"),
    ("3",  "Inventories"),
    ("4",  "U.S. government obligations"),
    ("5",  "Tax-exempt securities"),
    ("6",  "Other current assets (attach statement)"),
    ("7",  "Loans to shareholders"),
    ("8",  "Mortgage and real estate loans"),
    ("9",  "Other investments (attach statement)"),
    ("10a","Buildings and other depreciable assets"),
    ("10b","Less accumulated depreciation"),
    ("11a","Depletable assets"),
    ("11b","Less accumulated depletion"),
    ("12", "Land"),
    ("13a","Intangible assets"),
    ("13b","Less accumulated amortization"),
    ("14", "Other assets"),
    ("15", "Total assets"),
    ("16", "Accounts payable"),
    ("17", "Notes payable < 1 year"),
    ("18", "Other current liabilities"),
    ("19", "Loans from shareholders"),
    ("20", "Notes payable ≥ 1 year"),
    ("21", "Other liabilities"),
    ("22", "Capital stock"),
    ("23", "Additional paid-in capital"),
    ("24", "Retained earnings"),
    ("25", "Equity adjustments"),
    ("26", "Less treasury stock"),
    ("27", "Total liabilities & equity"),
]


def _pick(fields: dict, candidates: list[str]):
    for k in candidates:
        if k in fields and fields.get(k) not in (None, ""):
            return fields.get(k)
    return None


def _get_sched_l_value(fields: dict, line: str, col: str):
    """
    line: '1', '6', '10a', '10b'...
    col: 'c' or 'd'
    Handles keys in your JSON:
      - box6c, box1d
      - box10a-c, box10b-d
      - and fallback variants
    """
    candidates = [
        f"box{line}-{col}",   # box10a-c
        f"box{line}{col}",    # box6c, box1d
        f"box{line}_{col}",   # box10a_c (just in case)
        f"box{line} {col}",   # weird spacing
    ]
    return _pick(fields, candidates)


def _get_sched_l_note(fields: dict, line: str):
    """
    Notes/Statements thường nằm ở c (vd box6c='Statement #19', box18c='Statement #22')
    Ưu tiên lấy c, nếu không có thì thôi.
    """
    return _get_sched_l_value(fields, line, "c")


def export_schedule_l_excel(fields: dict, output_path: str):
    wb = Workbook()
    ws = wb.active
    ws.title = "Schedule L"

    # Title
    ws["A1"] = "Schedule L — Balance Sheets per Books (Form 1120-S)"
    ws.merge_cells("A1:E1")
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = Alignment(horizontal="center")

    # Header
    headers = ["Line", "Description", "Beginning (c)", "End (d)", "Notes / Statements"]
    ws.append(headers)

    header_fill = PatternFill("solid", fgColor="E6F0FF")
    thin = Side(style="thin", color="B0B0B0")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col in range(1, 6):
        c = ws.cell(row=2, column=col)
        c.font = Font(bold=True)
        c.fill = header_fill
        c.border = border
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    row = 3
    for line, desc in SCHEDULE_L_LINES:
        raw_c = _get_sched_l_value(fields, line, "c")
        raw_d = _get_sched_l_value(fields, line, "d")
        note = _get_sched_l_note(fields, line)
         # Nếu note là Statement thì đưa sang cột Notes, không điền vào cột (c)
        if isinstance(note, str) and note.strip().lower().startswith("statement"):
            raw_c = None
        else:
            # nếu không phải statement thì note không cần hiển thị (tránh lặp raw_c)
            note = None

        # >>> BỎ QUA DÒNG NẾU KHÔNG CÓ DATA
        if (raw_c in (None, "") and raw_d in (None, "") and note in (None, "")):
            continue
        
        ws.cell(row=row, column=1, value=line).border = border
        ws.cell(row=row, column=2, value=desc).border = border

        c_cell = ws.cell(row=row, column=3, value=raw_c)
        d_cell = ws.cell(row=row, column=4, value=raw_d)

        for cell in (c_cell, d_cell):
            cell.border = border
            cell.alignment = Alignment(horizontal="right", vertical="center")
            cell.number_format = "@"  # TEXT

        n_cell = ws.cell(row=row, column=5, value=note)
        n_cell.border = border
        n_cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        n_cell.number_format = "@"

        ws.cell(row=row, column=1).alignment = Alignment(horizontal="center")
        ws.cell(row=row, column=2).alignment = Alignment(wrap_text=True)

        row += 1

    # Column widths
    widths = [8, 55, 20, 20, 30]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A3"
    wb.save(output_path)
    return output_path
