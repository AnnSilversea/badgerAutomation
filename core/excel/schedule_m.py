"""
Excel export for Form 1120-S Schedule M-2
"""
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


SCHEDULE_M2_LINES = [
    ("1", "Balance at beginning of tax year"),
    ("2", "Ordinary income from page 1, line 22"),
    ("3", "Other additions (attach statement)"),
    ("4", "Loss from page 1, line 22"),
    ("5", "Other reductions (attach statement)"),
    ("6", "Combine lines 1 through 5"),
    ("7", "Distributions"),
    ("8", "Balance at end of tax year"),
]


def export_schedule_m2_excel(fields: dict, output_path: str):
    """
    Export Schedule M-2 to Excel.
    
    IMPORTANT: Preserves raw text format, does not convert parentheses to minus signs.
    
    :param fields: Dictionary of extracted fields (e.g., {"box1": "(1,720,659)", ...})
    :param output_path: Output Excel file path
    :return: Path to saved Excel file
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Schedule M-2"

    # Title
    ws["A1"] = "Schedule M-2 — Analysis of Accumulated Adjustments Account, Shareholders' Undistributed Taxable Income Previously Taxed, Accumulated E&P, and Other Adjustments Account (Form 1120-S)"
    ws.merge_cells("A1:F1")
    ws["A1"].font = Font(bold=True, size=12)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Header
    headers = ["Line", "Description",
               "(a) Accumulated Adjustments Account", 
               "(b) Shareholders' Undistributed Taxable Income Previously Taxed", 
               "(c) Accumulated Earnings and Profits", 
               "(d) Other Adjustments Account"]
    ws.append(headers)

    header_fill = PatternFill("solid", fgColor="E6F0FF")
    thin = Side(style="thin", color="B0B0B0")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col in range(1, 7):
        cell = ws.cell(row=2, column=col)
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.border = border
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Rows
    r = 3
    for line, desc in SCHEDULE_M2_LINES:
        # JSON key: box1..box8
        key = f"box{line}"
        raw_val = fields.get(key)

        ws.cell(row=r, column=1, value=line).border = border
        ws.cell(row=r, column=2, value=desc).border = border

        # Write raw value as TEXT to preserve parentheses
        a_cell = ws.cell(row=r, column=3, value=raw_val)
        a_cell.number_format = "@"  # TEXT
        a_cell.border = border
        a_cell.alignment = Alignment(horizontal="right", vertical="center")

        # Empty columns (b)(c)(d)
        for c in (4, 5, 6):
            cell = ws.cell(row=r, column=c, value=None)
            cell.number_format = "@"
            cell.border = border
            cell.alignment = Alignment(horizontal="right", vertical="center")

        ws.cell(row=r, column=1).alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=r, column=2).alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

        r += 1

    # Column widths
    widths = [8, 55, 18, 18, 22, 22]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A3"
    wb.save(output_path)
    return output_path

