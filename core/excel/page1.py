"""
Excel export for Form 1120-S Page 1
"""
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font


BOX_TO_1120_LINE = {
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

def export_form1120_to_excel(results: dict, excel_path: str, box_map: dict = None, page1_group: str = "pages_8_9"):
    """
    Export Form 1120-S Page 1 to Excel (mapping sheet + raw fields).
    
    :param results: Processing results dictionary
    :param excel_path: Output Excel file path
    :param box_map: Box to line mapping (defaults to BOX_TO_1120_LINE)
    :param page1_group: Page group name containing page 1 fields
    :return: Path to saved Excel file
    """
    if box_map is None:
        box_map = BOX_TO_1120_LINE

    wb = Workbook()
    ws = wb.active
    ws.title = "Form1120"
    ws.append(["Line", "Field", "Form1120s", ])

    for cell in ws[1]:
        cell.font = Font(bold=True)

    # Get fields from page1 group only (to avoid mixing with schedules)
    page1_payload = (results.get(page1_group, {}) or {})

    # NEW format (nested models)
    if isinstance(page1_payload.get("models"), dict) and page1_payload["models"]:
        model_payload = page1_payload["models"].get("Train_1120s_v2")
        if not model_payload:
            model_payload = next(iter(page1_payload["models"].values()))
        page1_fields = (model_payload.get("fields") or {})
    else:
        # OLD format
        page1_fields = (page1_payload.get("fields") or {})

    # ===== Map each box to row (SKIP empty) =====
    for box_key, info in box_map.items():
        val = page1_fields.get(box_key)
        if val in (None, ""):
            continue
        ws.append([info["line"], info["label"], val, ""])

    ws.column_dimensions["A"].width = 8   # Line
    ws.column_dimensions["B"].width = 48  # Field/Label
    ws.column_dimensions["C"].width = 22  # Value
    ws.column_dimensions["D"].width = 22  # Drake (empty)


    # Raw fields sheet for page1
    ws_raw = wb.create_sheet(f"{page1_group}_raw")
    ws_raw.append(["Field", "Value"])
    ws_raw["A1"].font = ws_raw["B1"].font = Font(bold=True)

    for k, v in page1_fields.items():
        # (optional) raw still writes everything for debug, including None
        ws_raw.append([k, v])

    ws_raw.column_dimensions["A"].width = 34
    ws_raw.column_dimensions["B"].width = 28

    wb.save(excel_path)
    return excel_path


def export_other_pages_to_excel(results: dict, excel_path: str, exclude_groups=None):
    """
    Export other pages (Schedule L/M...) to Excel as raw fields by group.
    
    :param results: Processing results dictionary
    :param excel_path: Output Excel file path
    :param exclude_groups: Set of group names to exclude (defaults to {"pages_8_9"})
    :return: Path to saved Excel file
    """
    """
    Export separate Excel file for remaining pages as raw fields.
    - If NEW pipeline: each group can have multiple models => create 1 sheet per model.
    - If OLD pipeline: 1 sheet / group as before.
    """
    if exclude_groups is None:
        exclude_groups = {"pages_8_9"}

    wb = Workbook()
    default = wb.active
    wb.remove(default)

    for group_name, payload in (results or {}).items():
        if group_name in exclude_groups:
            continue

        # NEW format
        if isinstance(payload.get("models"), dict) and payload["models"]:
            for model_id, model_payload in payload["models"].items():
                sheet_name = f"{group_name}__{model_id}"[:31]  # Excel limit 31 chars
                ws = wb.create_sheet(sheet_name)
                ws.append(["Field", "Value"])
                ws["A1"].font = ws["B1"].font = Font(bold=True)

                for k, v in (model_payload.get("fields") or {}).items():
                    ws.append([k, v])

                ws.column_dimensions["A"].width = 34
                ws.column_dimensions["B"].width = 28
        else:
            # OLD format
            ws = wb.create_sheet(group_name[:31])
            ws.append(["Field", "Value"])
            ws["A1"].font = ws["B1"].font = Font(bold=True)

            for k, v in (payload.get("fields") or {}).items():
                ws.append([k, v])

            ws.column_dimensions["A"].width = 34
            ws.column_dimensions["B"].width = 28

    wb.save(excel_path)
    return excel_path
