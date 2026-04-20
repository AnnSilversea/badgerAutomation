"""
Excel export functionality
Currently supports Form 1120-S
"""
import os
from typing import Dict, Any, Optional
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

# Import Excel modules from core.excel package
from .excel import (
    export_form1120_to_excel,
    export_other_pages_to_excel,
    export_schedule_l_excel,
    export_schedule_m2_excel,
    export_schedule_m1_excel,
    
)
# Import mapping functions
from .mapping import map_fields_to_line_label_value, get_mapping_for_model


def apply_edited_fields_to_results(results: Dict[str, Any], edited_fields: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Apply edited field values to results dictionary.
    
    :param results: Original results dictionary
    :param edited_fields: Dictionary mapping group_name -> {field_key: edited_value}
    :return: Results dictionary with edited values applied
    """
    # Create a deep copy to avoid modifying original
    import copy
    results_copy = copy.deepcopy(results)
    
    for group_name, group_data in results_copy.items():
        if not isinstance(group_data, dict):
            continue
        
        if group_name not in edited_fields:
            continue
        
        edited_group_fields = edited_fields[group_name]
        
        # Check if this group has models (nested structure)
        if isinstance(group_data.get("models"), dict) and group_data["models"]:
            # Apply edited values to each model's fields
            for model_id, model_data in group_data["models"].items():
                if isinstance(model_data, dict) and "fields" in model_data:
                    fields = model_data["fields"]
                    for field_key, edited_value in edited_group_fields.items():
                        if field_key in fields:
                            if isinstance(fields[field_key], dict):
                                fields[field_key] = fields[field_key].copy()
                                fields[field_key]['value'] = edited_value
                            else:
                                fields[field_key] = edited_value
        elif "fields" in group_data:
            # Direct fields structure
            fields = group_data["fields"]
            for field_key, edited_value in edited_group_fields.items():
                if field_key in fields:
                    if isinstance(fields[field_key], dict):
                        fields[field_key] = fields[field_key].copy()
                        fields[field_key]['value'] = edited_value
                    else:
                        fields[field_key] = edited_value
    
    return results_copy


def export_excel_files(
    form_type: str,
    results: Dict[str, Any],
    output_dir: str,
    config: Dict[str, Any]
) -> None:
    """
    Export Excel files based on form type and configuration
    
    :param form_type: Form type (currently only "1120s" supported)
    :param results: Processing results dictionary
    :param output_dir: Output directory for Excel files
    :param config: Excel export configuration
    """
    if form_type.lower() != "1120s":
        # Excel export currently only supported for 1120s
        return
    
    if not all([
        export_form1120_to_excel,
        export_other_pages_to_excel,
        export_schedule_l_excel,
        export_schedule_m2_excel,
        export_schedule_m1_excel
    ]):
        print("Warning: Excel export modules not available")
        return
    
    # Export Form 1120-S Page 1
    export_form1120_to_excel(
        results,
        os.path.join(output_dir, "1120s_form_page1.xlsx"),
        page1_group=config.get("page1_group", "pages_8_9")
    )
    
    # Export other pages
    export_other_pages_to_excel(
        results,
        os.path.join(output_dir, "1120s_other_pages.xlsx"),
        exclude_groups=config.get("exclude_groups", {"pages_8_9"})
    )
    
   # Export Schedule L (works for BOTH nested + old formats)
    schedule_l_group = config.get("schedule_l_group", "pages_12")
    if schedule_l_group in results:
        payload = results[schedule_l_group]

    # NEW: nested models
    if isinstance(payload.get("models"), dict) and payload["models"]:
        model_payload = payload["models"].get("Train_1120s_schedule_L_v4")
        if not model_payload:
            model_payload = next(iter(payload["models"].values()))  # fallback
        fields = model_payload.get("fields") or {}
    else:
        # OLD: direct fields
        fields = payload.get("fields") or {}

    if fields:
        export_schedule_l_excel(
            fields,
            os.path.join(output_dir, "ScheduleL_1120S.xlsx")
        )


    # Export Schedule M (nested models)
    schedule_m_group = config.get("schedule_m_group", "pages_13")
    if schedule_m_group in results and "models" in results[schedule_m_group]:
        models = results[schedule_m_group]["models"]

        # M1 (keep your correct model id)
        if "Train_1120s_scehdule_M1_v2" in models and "fields" in models["Train_1120s_scehdule_M1_v2"]:
            export_schedule_m1_excel(
                models["Train_1120s_scehdule_M1_v2"]["fields"],
                os.path.join(output_dir, "ScheduleM1_1120S.xlsx")
            )

        # M2
        if "Train_1120s_schedule_M2_v3" in models and "fields" in models["Train_1120s_schedule_M2_v3"]:
            export_schedule_m2_excel(
                models["Train_1120s_schedule_M2_v3"]["fields"],
                os.path.join(output_dir, "ScheduleM2_1120S.xlsx")
            )

    
    # # Export Schedule M-2
    # schedule_m_group = config.get("schedule_m2_group", "pages_13")
    # if schedule_m_group in results and "fields" in results[schedule_m_group]:
    #     export_schedule_m2_excel(
    #         results[schedule_m_group]["fields"],
    #         os.path.join(output_dir, "ScheduleM2_1120S.xlsx")
    #     )
    
    # schedule_m1_group = config.get("schedule_m1_group", "pages_14")
    # if schedule_m1_group in results and "fields" in results[schedule_m1_group]:
    #     export_schedule_m1_excel(
    #         results[schedule_m1_group]["fields"],
    #         os.path.join(output_dir, "ScheduleM1_1120S.xlsx")
    #     )
    

def generate_unified_excel(results: Dict[str, Any], excel_path: str, edited_fields: Optional[Dict[str, Dict[str, Any]]] = None) -> str:
    """
    Generate a single Excel file with multiple sheets (one per section).
    Each sheet contains Line, Label, Value columns.
    
    :param results: Merged results dictionary from pipeline
    :param excel_path: Output path for Excel file
    :param edited_fields: Optional dictionary of edited field values by group name and field key
    :return: Path to saved Excel file
    """
    # Apply edited fields to results if provided
    if edited_fields:
        results = apply_edited_fields_to_results(results, edited_fields)
    wb = Workbook()
    # Remove default sheet
    if wb.active:
        wb.remove(wb.active)
    
    # Model ID to Section name mappings
    model_id_to_section = {
        # Form 1120S mappings
        "Train_1120s_v2": "Form 1120S",
        "Train_1120s_schedule_L_v4": "Schedule L",  # v3 version
        "Train_1120s_scehdule_M1_v2": "Schedule M-1",
        "Train_1120s_schedule_M2_v3": "Schedule M-2",
        # Form 1120 mappings
        "Train_1120_v2": "Form 1120",
        "Train_1120_schedule_L_v3": "Schedule L",
        "Train_1120_schedule_M1_v2": "Schedule M-1",
        "Train_1120_schedule_M2_v3": "Schedule M-2",
        # Form 1065 mappings
        "Train_model_1065_v4": "Form 1065",
        "Train_1065_schedule_L_v4": "Schedule L",
        "Train_1065_schedule_m1_v2": "Schedule M-1",
        "Train_1065_schedule_m2_v3": "Schedule M-2",
        # Form 1040 mappings
        "prebuilt-tax.us.1040": "Form 1040",
        # Form 1099-DIV mappings
        "prebuilt-tax.us.1099DIV": "Form 1099-DIV",
        # Form 1099-INT mappings
        "prebuilt-tax.us.1099INT": "Form 1099-INT",
        # Form 1099-MISC mappings
        "prebuilt-tax.us.1099MISC": "Form 1099-MISC",
        # Form 1099-NEC mappings
        "prebuilt-tax.us.1099NEC": "Form 1099-NEC",
        # Form 1099-R mappings
        "prebuilt-tax.us.1099R": "Form 1099-R",
        # Form 1099-SSA mappings
        "prebuilt-tax.us.1099SSA": "Form 1099-SSA",
        # Form W-2 mappings
        "Train_model_w2_v4": "Form W-2",
    }
    
    # Group name to display name mappings
    group_display_names = {
        "pages_8_9": "Form 1120S",
        "pages_12": "Schedule L",
        "pages_13": "Schedule M",
        "pages_14": "Schedule M-1",
        "Form_1120": "Form 1120",
        "Form_1040": "Form 1040",
        "Form_1099DIV": "Form 1099-DIV",
        "Form_1099INT": "Form 1099-INT",
        "Form_1099MISC": "Form 1099-MISC",
        "Form_1099NEC": "Form 1099-NEC",
        "Form_1099R": "Form 1099-R",
        "Form_1099SSA": "Form 1099-SSA",
        "Form_W2": "Form W-2",
    }
    
    # Iterate through results sections
    for group_name, group_data in results.items():
        if not isinstance(group_data, dict):
            continue
        
        # Check if this group has models (nested structure)
        if isinstance(group_data.get("models"), dict) and group_data["models"]:
            # Create a sheet for each model
            for model_id, model_data in group_data["models"].items():
                if not isinstance(model_data, dict):
                    continue
                
                fields = model_data.get("fields", {})
                if not fields:
                    continue
                
                # Get section name
                section_name = model_id_to_section.get(model_id, model_id)
                # Sanitize sheet name (Excel limit: 31 characters)
                sheet_name = section_name[:31]
                
                # Check if sheet already exists (handle duplicates)
                if sheet_name in wb.sheetnames:
                    sheet_name = f"{section_name[:25]}_{len([s for s in wb.sheetnames if s.startswith(section_name[:25])])}"
                    sheet_name = sheet_name[:31]
                
                # Create sheet
                ws = wb.create_sheet(sheet_name)
                
                # Add header row
                headers = ["Line", "Label", "Value"]
                ws.append(headers)
                
                # Style header row
                header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                header_font = Font(bold=True, color="FFFFFF")
                border = Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )
                
                for cell in ws[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.border = border
                    cell.alignment = Alignment(horizontal='left', vertical='center')
                
                # Check if fields are already mapped (have Line, Label, Value structure)
                # This happens when pipeline has already applied mapping via apply_mapping_to_result
                sample_field = next(iter(fields.values())) if fields else None
                is_already_mapped = (
                    sample_field and 
                    isinstance(sample_field, dict) and 
                    "line" in sample_field and 
                    "label" in sample_field and 
                    "value" in sample_field
                )
                
                if is_already_mapped:
                    # Fields are already mapped by pipeline, use them directly
                    mapped_fields = fields
                else:
                    # Fields need to be mapped (for backward compatibility with old data)
                    mapped_fields = map_fields_to_line_label_value(fields, model_id)
                
                # Add data rows
                for field_name, field_data in mapped_fields.items():
                    if isinstance(field_data, dict):
                        line = field_data.get("line", "")
                        label = field_data.get("label", field_name)
                        value = field_data.get("value", "")
                        
                        # Handle nested dictionaries (if value is still a dict)
                        if isinstance(value, dict):
                            # If value is a dict, try to extract the actual value
                            # Check if it has a 'value' key
                            if "value" in value:
                                value = value["value"]
                            # Otherwise convert the whole dict to string
                            else:
                                value = str(value)
                        # Convert value to string if it's not a simple type
                        elif not isinstance(value, (str, int, float, type(None), bool)):
                            value = str(value) if value is not None else ""
                    else:
                        # Fallback if field_data is not a dict
                        line = ""
                        label = field_name
                        value = field_data if field_data is not None else ""
                        # Convert to string if not a simple type
                        if not isinstance(value, (str, int, float, type(None), bool)):
                            value = str(value) if value is not None else ""
                    
                    # Ensure all values are Excel-compatible (string, number, or None)
                    if value is None:
                        value = ""
                    elif isinstance(value, (list, dict)):
                        value = str(value)
                    elif isinstance(value, bool):
                        value = "True" if value else "False"
                    
                    # Skip empty values if desired, or include them
                    ws.append([line, label, value])
                
                # Apply borders to data rows
                for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
                    for cell in row:
                        cell.border = border
                        cell.alignment = Alignment(horizontal='left', vertical='center')
                
                # Set column widths
                ws.column_dimensions['A'].width = 10  # Line
                ws.column_dimensions['B'].width = 50  # Label
                ws.column_dimensions['C'].width = 20  # Value
                
                # Freeze header row
                ws.freeze_panes = 'A2'
                
                # Handle Box12 for W2 forms (if present)
                if model_id in ("Train_model_w2_v4"):
                    box12_data = model_data.get("box12")
                    if box12_data and isinstance(box12_data, dict):
                        # Add Box12 entries to the same sheet
                        for field_name, field_data in box12_data.items():
                            if isinstance(field_data, dict):
                                line = field_data.get("line", "")
                                label = field_data.get("label", field_name)
                                value = field_data.get("value", "")
                                
                                # Convert value to Excel-compatible format
                                if value is None:
                                    value = ""
                                elif isinstance(value, (list, dict)):
                                    value = str(value)
                                elif isinstance(value, bool):
                                    value = "True" if value else "False"
                                elif not isinstance(value, (str, int, float)):
                                    value = str(value) if value is not None else ""
                                
                                ws.append([line, label, value])
                        
                        # Reapply borders to new rows
                        for row in ws.iter_rows(min_row=ws.max_row - len(box12_data) + 1, max_row=ws.max_row):
                            for cell in row:
                                cell.border = border
                                cell.alignment = Alignment(horizontal='left', vertical='center')
        
        elif group_data.get("fields"):
            # Direct fields structure (old format)
            fields = group_data.get("fields", {})
            if fields is None:
                continue
            
            # Get section name
            section_name = group_display_names.get(group_name, group_name)
            # Sanitize sheet name
            sheet_name = section_name[:31]
            
            # Check if sheet already exists
            if sheet_name in wb.sheetnames:
                sheet_name = f"{section_name[:25]}_{len([s for s in wb.sheetnames if s.startswith(section_name[:25])])}"
                sheet_name = sheet_name[:31]
            
            # Create sheet
            ws = wb.create_sheet(sheet_name)
            
            # Add header row
            headers = ["Line", "Label", "Value"]
            ws.append(headers)
            
            # Style header row
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")
            border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.border = border
                cell.alignment = Alignment(horizontal='left', vertical='center')
            
            # Check if fields are already mapped (have Line, Label, Value structure)
            sample_field = next(iter(fields.values())) if fields else None
            if isinstance(sample_field, dict) and "line" in sample_field and "label" in sample_field:
                # Fields are already mapped
                for field_name, field_data in fields.items():
                    if isinstance(field_data, dict):
                        line = field_data.get("line", "")
                        label = field_data.get("label", field_name)
                        value = field_data.get("value", "")
                        
                        # Handle nested dictionaries (if value is still a dict)
                        if isinstance(value, dict):
                            # If value is a dict, try to extract the actual value
                            # Check if it has a 'value' key
                            if "value" in value:
                                value = value["value"]
                            # Otherwise convert the whole dict to string
                            else:
                                value = str(value)
                        # Convert value to string if it's not a simple type
                        elif not isinstance(value, (str, int, float, type(None), bool)):
                            value = str(value) if value is not None else ""
                    else:
                        line = ""
                        label = field_name
                        value = field_data if field_data is not None else ""
                        # Convert to string if not a simple type
                        if not isinstance(value, (str, int, float, type(None), bool)):
                            value = str(value) if value is not None else ""
                    
                    # Ensure all values are Excel-compatible
                    if value is None:
                        value = ""
                    elif isinstance(value, (list, dict)):
                        value = str(value)
                    elif isinstance(value, bool):
                        value = "True" if value else "False"
                    
                    ws.append([line, label, value])
            else:
                # Fields are not mapped, use field name as label
                for field_name, value in fields.items():
                    # Convert value to Excel-compatible format
                    if value is None:
                        excel_value = ""
                    elif isinstance(value, (list, dict)):
                        excel_value = str(value)
                    elif isinstance(value, bool):
                        excel_value = "True" if value else "False"
                    elif not isinstance(value, (str, int, float)):
                        excel_value = str(value)
                    else:
                        excel_value = value
                    ws.append(["", field_name, excel_value])
            
            # Apply borders to data rows
            for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
                for cell in row:
                    cell.border = border
                    cell.alignment = Alignment(horizontal='left', vertical='center')
            
            # Set column widths
            ws.column_dimensions['A'].width = 10  # Line
            ws.column_dimensions['B'].width = 50  # Label
            ws.column_dimensions['C'].width = 20  # Value
            
            # Freeze header row
            ws.freeze_panes = 'A2'
            
            # Handle Box12 for W2 forms (if present in direct fields structure)
            if group_name == "Form_W2":
                box12_data = group_data.get("box12")
                if box12_data and isinstance(box12_data, dict):
                    for field_name, field_data in box12_data.items():
                        if isinstance(field_data, dict):
                            line = field_data.get("line", "")
                            label = field_data.get("label", field_name)
                            value = field_data.get("value", "")
                            
                            # Convert value to Excel-compatible format
                            if value is None:
                                value = ""
                            elif isinstance(value, (list, dict)):
                                value = str(value)
                            elif isinstance(value, bool):
                                value = "True" if value else "False"
                            elif not isinstance(value, (str, int, float)):
                                value = str(value) if value is not None else ""
                            
                            ws.append([line, label, value])
                    
                    # Reapply borders to new rows
                    for row in ws.iter_rows(min_row=ws.max_row - len(box12_data) + 1, max_row=ws.max_row):
                        for cell in row:
                            cell.border = border
                            cell.alignment = Alignment(horizontal='left', vertical='center')
    
    # Handle state/local taxes table for W2 forms
    # Check if any group has state_local_taxes data
    for group_name, group_data in results.items():
        if not isinstance(group_data, dict):
            continue
        
        # Check nested models structure
        if isinstance(group_data.get("models"), dict) and group_data["models"]:
            for model_id, model_data in group_data["models"].items():
                if model_id in ("Train_model_w2_v4"):
                    state_local_data = model_data.get("state_local_taxes")
                    if state_local_data and isinstance(state_local_data, dict):
                        create_state_local_taxes_sheet(wb, state_local_data)
                        break
                # Handle 1099-DIV state taxes withheld in nested models
                elif model_id == "prebuilt-tax.us.1099DIV":
                    state_taxes_data = model_data.get("state_taxes_withheld")
                    if state_taxes_data and isinstance(state_taxes_data, dict):
                        create_state_taxes_withheld_sheet(wb, state_taxes_data, "1099-DIV")
                # Handle 1099-INT state taxes withheld in nested models
                elif model_id == "prebuilt-tax.us.1099INT":
                    state_taxes_data = model_data.get("state_taxes_withheld")
                    if state_taxes_data and isinstance(state_taxes_data, dict):
                        create_state_taxes_withheld_sheet(wb, state_taxes_data, "1099-INT")
                # Handle 1099-MISC state taxes withheld in nested models
                elif model_id == "prebuilt-tax.us.1099MISC":
                    state_taxes_data = model_data.get("state_taxes_withheld")
                    if state_taxes_data and isinstance(state_taxes_data, dict):
                        create_state_taxes_withheld_sheet(wb, state_taxes_data, "1099-MISC")
                # Handle 1099-NEC state taxes withheld in nested models
                elif model_id == "prebuilt-tax.us.1099NEC":
                    state_taxes_data = model_data.get("state_taxes_withheld")
                    if state_taxes_data and isinstance(state_taxes_data, dict):
                        create_state_taxes_withheld_sheet(wb, state_taxes_data, "1099-NEC")
                # Handle 1099-R state taxes withheld in nested models
                elif model_id == "prebuilt-tax.us.1099R":
                    state_taxes_data = model_data.get("state_taxes_withheld")
                    if state_taxes_data and isinstance(state_taxes_data, dict):
                        create_state_taxes_withheld_sheet(wb, state_taxes_data, "1099-R")
                    # Handle 1099-R local taxes withheld in nested models
                    local_taxes_data = model_data.get("local_taxes_withheld")
                    if local_taxes_data and isinstance(local_taxes_data, dict):
                        create_state_taxes_withheld_sheet(wb, local_taxes_data, "1099-R Local")
        # Check direct fields structure
        elif group_name == "Form_W2":
            state_local_data = group_data.get("state_local_taxes")
            if state_local_data and isinstance(state_local_data, dict):
                create_state_local_taxes_sheet(wb, state_local_data)
        
        # Handle 1099-DIV state taxes withheld (direct structure)
        if group_name == "Form_1099DIV":
            state_taxes_data = group_data.get("state_taxes_withheld")
            if state_taxes_data and isinstance(state_taxes_data, dict):
                create_state_taxes_withheld_sheet(wb, state_taxes_data, "1099-DIV")
        
        # Handle 1099-INT state taxes withheld (direct structure)
        if group_name == "Form_1099INT":
            state_taxes_data = group_data.get("state_taxes_withheld")
            if state_taxes_data and isinstance(state_taxes_data, dict):
                create_state_taxes_withheld_sheet(wb, state_taxes_data, "1099-INT")
        
        # Handle 1099-NEC state taxes withheld (direct structure)
        if group_name == "Form_1099NEC":
            state_taxes_data = group_data.get("state_taxes_withheld")
            if state_taxes_data and isinstance(state_taxes_data, dict):
                create_state_taxes_withheld_sheet(wb, state_taxes_data, "1099-NEC")
        
        # Handle 1099-MISC state taxes withheld (direct structure)
        if group_name == "Form_1099MISC":
            state_taxes_data = group_data.get("state_taxes_withheld")
            if state_taxes_data and isinstance(state_taxes_data, dict):
                create_state_taxes_withheld_sheet(wb, state_taxes_data, "1099-MISC")
        
        # Handle 1099-R state taxes withheld (direct structure)
        if group_name == "Form_1099R":
            state_taxes_data = group_data.get("state_taxes_withheld")
            if state_taxes_data and isinstance(state_taxes_data, dict):
                create_state_taxes_withheld_sheet(wb, state_taxes_data, "1099-R")
            # Handle 1099-R local taxes withheld (direct structure)
            local_taxes_data = group_data.get("local_taxes_withheld")
            if local_taxes_data and isinstance(local_taxes_data, dict):
                create_state_taxes_withheld_sheet(wb, local_taxes_data, "1099-R Local")
    
    # If no sheets were created, create a default empty sheet
    if len(wb.sheetnames) == 0:
        ws = wb.create_sheet("Data")
        ws.append(["Line", "Label", "Value"])
        for cell in ws[1]:
            cell.font = Font(bold=True)
    
    # Save workbook
    wb.save(excel_path)
    return excel_path


def create_state_local_taxes_sheet(wb: Workbook, state_local_data: Dict[str, Any]) -> None:
    """
    Create "State & Local Taxes" sheet with table format.
    Columns: Line, Label, then one column per state alias (e.g., OH_1, OH_2) with display headers
    showing the base state name (e.g., OH, OH) when duplicates exist.
    
    :param wb: Workbook to add sheet to
    :param state_local_data: Dictionary with 'rows', 'states', and optional 'state_labels' keys from transform_state_local_table
    """
    if not isinstance(state_local_data, dict):
        return
    
    rows = state_local_data.get("rows", [])
    states = state_local_data.get("states", [])
    state_labels = state_local_data.get("state_labels", states)
    
    if not rows or not states:
        return
    
    # Fallback if lengths mismatch
    if len(state_labels) != len(states):
        state_labels = states
    
    # Create sheet
    sheet_name = "State & Local Taxes"
    # Check if sheet already exists
    if sheet_name in wb.sheetnames:
        sheet_name = f"State & Local Taxes_{len([s for s in wb.sheetnames if s.startswith('State & Local Taxes')])}"
        sheet_name = sheet_name[:31]  # Excel limit
    
    ws = wb.create_sheet(sheet_name)
    
    # Create header row: Line, Label, [state display labels...]
    headers = ["Line", "Label"] + state_labels
    ws.append(headers)
    
    # Style header row
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal='left', vertical='center')
    
    # Add data rows
    for row_data in rows:
        line = row_data.get("line", "")
        label = row_data.get("label", "")
        row_values = [line, label]
        
        # Add values for each state alias
        for state in states:
            value = row_data.get(state, "")
            if value is None:
                value = ""
            elif isinstance(value, (list, dict)):
                value = str(value)
            elif isinstance(value, bool):
                value = "True" if value else "False"
            elif not isinstance(value, (str, int, float)):
                value = str(value) if value is not None else ""
            row_values.append(value)
        
        ws.append(row_values)
    
    # Apply borders to data rows
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(horizontal='left', vertical='center')
    
    # Set column widths
    ws.column_dimensions['A'].width = 10  # Line
    ws.column_dimensions['B'].width = 40  # Label
    for idx in range(3, len(states) + 3):
        col_letter = get_column_letter(idx)
        ws.column_dimensions[col_letter].width = 20  # State columns
    
    # Freeze header row
    ws.freeze_panes = 'A2'


def create_state_taxes_withheld_sheet(wb: Workbook, state_taxes_data: Dict[str, Any], form_type: str = "1099-DIV") -> None:
    """
    Create "State Tax Withheld (1099-DIV)", "State Tax Withheld (1099-INT)", "State Tax Information (1099-MISC)", or
    "State Tax Withheld (1099-NEC)" sheet with table format.
    Columns vary by form type:
    - 1099-DIV/INT: State, State identification no., State tax withheld
    - 1099-MISC/NEC: State tax withheld, State/Payer's state no., State income
    Rows: One row per StateTaxesWithheld entry
    
    :param wb: Workbook to add sheet to
    :param state_taxes_data: Dictionary with rows and fields
    :param form_type: Form type ("1099-DIV", "1099-INT", or "1099-MISC")
    """
    if not isinstance(state_taxes_data, dict):
        return
    
    rows = state_taxes_data.get("rows", [])
    fields = state_taxes_data.get("fields", [])
    
    if not rows:
        return
    
    # Determine sheet name and header labels based on form type
    if form_type == "1099-MISC":
        base_sheet_name = "State Tax Information (1099-MISC)"
        # Default fields for 1099-MISC if not provided
        if not fields:
            fields = ["StateTaxWithheld", "StateIdentificationNumber", "StateIncome"]
        header_labels = [
            "State tax withheld",
            "State/Payer's state no.",
            "State income"
        ]
    elif form_type == "1099-NEC":
        base_sheet_name = "State Tax Withheld (1099-NEC)"
        # Default fields for 1099-NEC if not provided
        if not fields:
            fields = ["StateTaxWithheld", "StateIdentificationNumber", "StateIncome"]
        header_labels = [
            "State tax withheld",
            "State/Payer's state no.",
            "State income"
        ]
    elif form_type == "1099-R Local":
        base_sheet_name = "Local Tax Withheld (1099-R Local)"
        # Default fields for 1099-R Local if not provided
        if not fields:
            fields = ["LocalTaxWithheld", "LocalityName", "LocalDistribution"]
        header_labels = [
            "Local tax withheld",
            "Name of locality",
            "Local distribution"
        ]
    elif form_type == "1099-R":
        base_sheet_name = "State Tax Withheld (1099-R)"
        # Default fields for 1099-R if not provided
        if not fields:
            fields = ["StateTaxWithheld", "StateIdentificationNumber", "StateDistribution"]
        header_labels = [
            "State tax withheld",
            "State/Payer's state no.",
            "State distribution"
        ]
    else:
        base_sheet_name = f"State Tax Withheld ({form_type})"
        # Default fields for 1099-DIV/INT if not provided
        if not fields:
            fields = ["State", "StateIdentificationNumber", "StateTaxWithheld"]
        header_labels = [
            "State",
            "State identification no.",
            "State tax withheld"
        ]
    
    sheet_name = base_sheet_name
    if sheet_name in wb.sheetnames:
        sheet_name = f"{base_sheet_name}_{len([s for s in wb.sheetnames if s.startswith(base_sheet_name)])}"
        sheet_name = sheet_name[:31]  # Excel limit
    
    ws = wb.create_sheet(sheet_name)
    
    # Header (display labels)
    ws.append(header_labels)
    
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal='left', vertical='center')
    
    # Rows
    for row_data in rows:
        row_values = []
        for field_name in fields:
            value = row_data.get(field_name, "")
            if value is None:
                value = ""
            elif isinstance(value, (list, dict)):
                value = str(value)
            elif isinstance(value, bool):
                value = "True" if value else "False"
            elif not isinstance(value, (str, int, float)):
                value = str(value) if value is not None else ""
            row_values.append(value)
        ws.append(row_values)
    
    # Apply borders
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(horizontal='left', vertical='center')
    
    # Column widths - different for 1099-MISC vs 1099-DIV/INT
    if form_type in ("1099-MISC", "1099-NEC"):
        width_map = {
            "StateTaxWithheld": 18,
            "StateIdentificationNumber": 28,
            "StateIncome": 18,
        }
    else:
        width_map = {
            "State": 12,
            "StateIdentificationNumber": 28,
            "StateTaxWithheld": 18,
        }
    for idx, field_name in enumerate(fields, start=1):
        col_letter = get_column_letter(idx)
        ws.column_dimensions[col_letter].width = width_map.get(field_name, 18)
    
    ws.freeze_panes = 'A2'
