from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


SCHEDULE_M1_ROWS = [
    ("main", "1", "Net income (loss) per books", "box1"),
    ("main", "2", "Income included on Schedule K, lines 1, 2, 3, 4, 5a, 6, 7, 8a, 9, and 10, not recorded on books this year (itemize):", "box2"),
    ("main", "3", "Expenses recorded on books this year not included on Schedule K, lines 1 through 12e, and 16f (itemize):", "box3"),
    ("main", "4", "Add lines 1 through 3", "box4"),
    ("main", "5", "Income recorded on books this year not included on Schedule K, lines 1 through 10 (itemize):", "box5"),
    ("main", "6", "Deductions included on Schedule K, lines 1 through 12e, and 16f, not charged against book income this year (itemize):", "box6"),
    ("main", "7", "Add lines 5 and 6", "box7"),
    ("main", "8", "Income (loss) (Subtract line 7 from line 4)", "box8"),
]



def export_schedule_m1_excel(fields: dict, output_path: str):
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Schedule M-1"

    # ===== Title =====
    ws["A1"] = "Schedule M-1 — Reconciliation of Income (Loss) per Books With Income (Loss) per Return (Form 1120-S)"
    ws.merge_cells("A1:C1")
    ws["A1"].font = Font(bold=True, size=12)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Optional note (giống form)
    ws["A2"] = "Note: The corporation may be required to file Schedule M-3. See instructions."
    ws.merge_cells("A2:C2")
    ws["A2"].font = Font(italic=True, size=10)
    ws["A2"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # ===== Header =====
    headers = ["Line", "Description", "Amount"]
    ws.append(headers)  # row 3

    header_fill = PatternFill("solid", fgColor="E6F0FF")
    thin = Side(style="thin", color="B0B0B0")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col in range(1, 4):
        cell = ws.cell(row=3, column=col)
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.border = border
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # ===== Body rows =====
    r = 4
    for row_type, line, desc, key in SCHEDULE_M1_ROWS:
        raw_val = fields.get(key)

        # Line
        c1 = ws.cell(row=r, column=1, value=line)
        c1.border = border
        c1.alignment = Alignment(horizontal="center", vertical="center")

        # Description with indent for sublines
        c2 = ws.cell(row=r, column=2, value=desc)
        c2.border = border
        if row_type == "sub":
            c2.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=2)
            c2.font = Font(size=11)
        else:
            c2.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            c2.font = Font(bold=False, size=11)

        # Amount as TEXT to preserve parentheses/commas
        c3 = ws.cell(row=r, column=3, value=raw_val)
        c3.number_format = "@"  # TEXT
        c3.border = border
        c3.alignment = Alignment(horizontal="right", vertical="center")

        r += 1

    # ===== Column widths =====
    widths = [10, 75, 18]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A4"
    wb.save(output_path)
    return output_path
