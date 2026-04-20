"""
Form type configurations
"""
from typing import Dict, List, Union
from dataclasses import dataclass


@dataclass
class FormConfig:
    """Configuration for a tax form type"""
    form_type: str
    merged_json_filename: str
    page_groups: Dict[str, List[int]]
    model_map: Dict[str, Union[str, List[str]]]
    use_nested_models: bool = False  # True for 1065/1120, False for 1120s
    excel_export: bool = False  # True for 1120s
    excel_config: Dict = None


# Form configurations
FORM_CONFIGS = {
    "1065": FormConfig(
        form_type="1065",
        merged_json_filename="1065_merged.json",
        page_groups={
            "Form_1065": [9],
            "Schedule_M_L": [14]
        },
        model_map={
            "Form_1065": ["Train_model_1065_v4"],
            "Schedule_M_L": [
                "Train_1065_schedule_m2_v3",
                "Train_1065_schedule_m1_v2",
                "Train_1065_schedule_L_v4",
            ],
        },
        use_nested_models=True,
        excel_export=False,
    ),
    "1120": FormConfig(
        form_type="1120",
        merged_json_filename="1120_merged.json",
        page_groups={
            "Form_1120": [4],
            "Schedule_M_L_1120": [9]
        },
        model_map={
            "Form_1120": ["Train_1120_v2"],
            "Schedule_M_L_1120": [
                "Train_1120_schedule_L_v3",
                "Train_1120_schedule_M2_v3",
                "Train_1120_schedule_M1_v2",
            ],
        },
        use_nested_models=True,
        excel_export=False,
    ),
    "1120s": FormConfig(
        form_type="1120s",
        merged_json_filename="1120S_merged.json",
        page_groups={
            "pages_8_9": [7, 8],
            "pages_12": [10, 11],
            "pages_13": [11],
        },
        model_map={
            "pages_8_9": "Train_1120s_v2",
            "pages_12": "Train_1120s_schedule_L_v4",
            "pages_13": ["Train_1120s_scehdule_M1_v2", "Train_1120s_schedule_M2_v3"],
        },
        use_nested_models=False,
        excel_export=True,
        excel_config={
            "page1_group": "pages_8_9",
            "exclude_groups": {"pages_8_9"},
            "schedule_l_group": "pages_12",
            "schedule_m_group": "pages_13",
        }
    ),
    "1040": FormConfig(
        form_type="1040",
        merged_json_filename="1040_merged.json",
        page_groups={
            "Form_1040": [0,1],
        },
        model_map={
            "Form_1040": ["prebuilt-tax.us.1040"],
        }
    ),
    "1099div": FormConfig(
        form_type="1099DIV",
        merged_json_filename="1099DIV_merged.json",
        page_groups={
            "Form_1099DIV": [0],
        },
        model_map={
            "Form_1099DIV": ["prebuilt-tax.us.1099DIV"],
        }
    ),
    "1099int": FormConfig(
        form_type="1099INT",
        merged_json_filename="1099INT_merged.json",
        page_groups={
            "Form_1099INT": [0],
        },
        model_map={
            "Form_1099INT": ["prebuilt-tax.us.1099INT"],
        }
    ),
    "1099misc": FormConfig(
        form_type="1099MISC",
        merged_json_filename="1099MISC_merged.json",
        page_groups={
            "Form_1099MISC": [0],
        },
        model_map={
            "Form_1099MISC": ["prebuilt-tax.us.1099MISC"],
        }
    ),
    "1099nec": FormConfig(
        form_type="1099NEC",
        merged_json_filename="1099NEC_merged.json",
        page_groups={
            "Form_1099NEC": [0],
        },
        model_map={
            "Form_1099NEC": ["prebuilt-tax.us.1099NEC"],
        }
    ),
    "w2": FormConfig(
        form_type="W2",
        merged_json_filename="W2_merged.json",
        page_groups={
            "Form_W2": [0],
        },
        model_map={
            "Form_W2": ["Train_model_w2_v4"],
        }
    ),
    "w2g": FormConfig(
        form_type="W2G",
        merged_json_filename="W2G_merged.json",
        page_groups={
            "Form_W2G": [0],
        },
        model_map={
            "Form_W2G": ["model_w2g_v1"],
        }
    ),
    "1099r": FormConfig(
        form_type="1099R",
        merged_json_filename="1099R_merged.json",
        page_groups={
            "Form_1099R": [0],
        },
        model_map={
            "Form_1099R": ["prebuilt-tax.us.1099R"],
        }
    ),
    "1099ssa": FormConfig(
        form_type="1099SSA",
        merged_json_filename="1099SSA_merged.json",
        page_groups={
            "Form_1099SSA": [0],
        },
        model_map={
            "Form_1099SSA": ["prebuilt-tax.us.1099SSA"],
        }
    ),
}

# Mapping from AI_Page detection keys to config page_groups per form type
# AI_Page detects: page1, schedule_l, schedule_m1, schedule_m2, form_1040_page, w2_pages, 1099_*_pages
# This maps those detected keys to the appropriate page_group names in FORM_CONFIGS
PAGE_DETECTION_MAPPING = {
    "1120s": {
        # page1 maps to Form 1120S main pages
        "page1": "pages_8_9",
        # schedule_l maps to Schedule L pages
        "schedule_l": "pages_12",
        # schedule_m1 and schedule_m2 both map to Schedule M pages
        "schedule_m1": "pages_13",
        "schedule_m2": "pages_13",
    },
    "1065": {
        # page1 maps to Form 1065 main page
        "page1": "Form_1065",
        # All schedule pages map to combined Schedule_M_L group
        "schedule_l": "Schedule_M_L",
        "schedule_m1": "Schedule_M_L",
        "schedule_m2": "Schedule_M_L",
    },
    "1120": {
        # page1 maps to Form 1120 main page
        "page1": "Form_1120",
        # All schedule pages map to combined Schedule_M_L_1120 group
        "schedule_l": "Schedule_M_L_1120",
        "schedule_m1": "Schedule_M_L_1120",
        "schedule_m2": "Schedule_M_L_1120",
    },
    "1040": {
        # form_1040_page maps to Form 1040
        "form_1040_page": "Form_1040",
    },
    "w2": {
        # w2_pages maps to Form W-2
        "w2_pages": "Form_W2",
    },
    "w2g": {
        # w2_pages also applies for W-2G detection
        "w2_pages": "Form_W2G",
    },
    "1099div": {
        # 1099_div_pages maps to Form 1099-DIV
        "1099_div_pages": "Form_1099DIV",
    },
    "1099int": {
        # 1099_int_pages maps to Form 1099-INT
        "1099_int_pages": "Form_1099INT",
    },
    "1099misc": {
        # Generic 1099 detection - user may need to verify
        "1099_nec_pages": "Form_1099MISC",
    },
    "1099nec": {
        # 1099_nec_pages maps to Form 1099-NEC
        "1099_nec_pages": "Form_1099NEC",
    },
    "1099r": {
        # 1099_r_pages maps to Form 1099-R
        "1099_r_pages": "Form_1099R",
    },
    "1099ssa": {
        # 1099_ssa_pages maps to Form 1099-SSA
        "1099_ssa_pages": "Form_1099SSA",
    },
}


def get_form_config(form_type: str) -> FormConfig:
    """Get configuration for a form type"""
    form_type_lower = form_type.lower()
    if form_type_lower not in FORM_CONFIGS:
        raise ValueError(f"Unknown form type: {form_type}. Supported: {list(FORM_CONFIGS.keys())}")
    return FORM_CONFIGS[form_type_lower]


def get_page_detection_mapping(form_type: str) -> Dict[str, str]:
    """Get the AI detection key to page_group mapping for a form type"""
    form_type_lower = form_type.lower()
    return PAGE_DETECTION_MAPPING.get(form_type_lower, {})

