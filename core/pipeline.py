"""
Unified pipeline for processing tax documents
"""
import os
import json
import logging
import time
from typing import Dict, Any, List, Union

from .config import FormConfig, get_form_config
from .utils import split_pdf_by_page_groups
from .azure_client import analyze_pdf_with_model
from .mapping import apply_mapping_to_result
from DrakeAutomation.mapping import map_fields_with_label_and_value

from DrakeAutomation.ocr_normalization import (
    normalize_1099_div,
    normalize_1099_int,
    normalize_1099_r,
    normalize_1099_ssa,
    normalize_w2
)

# Configure logging
logger = logging.getLogger(__name__)


def _normalize_raw_result(raw_res: Dict[str, Any], model_id: str) -> Dict[str, Any]:
    """Normalize raw result from Azure DI based on model_id."""
    if not raw_res:
        return raw_res

    if model_id == "prebuilt-tax.us.1099DIV":
        return normalize_1099_div(raw_res)
    elif model_id == "prebuilt-tax.us.1099INT":
        return normalize_1099_int(raw_res)
    elif model_id == "prebuilt-tax.us.1099R":
        return normalize_1099_r(raw_res)
    elif model_id == "prebuilt-tax.us.1099SSA":
        return normalize_1099_ssa(raw_res)
    elif model_id == "Train_model_w2_v4":
        return normalize_w2(raw_res)
    
    return raw_res


def run_pipeline(form_type: str, input_pdf: str, output_root: str, custom_page_groups: Dict[str, List[int]] = None, for_drake: bool = False) -> Dict[str, Any]:
    """
    Run the processing pipeline for a tax document
    
    :param form_type: Form type ("1065", "1120", or "1120s")
    :param input_pdf: Path to input PDF file
    :param output_root: Output directory for results
    :param custom_page_groups: Optional custom page groups dict. If provided, overrides config defaults.
    :return: Dictionary containing processing results
    """
    start_time = time.time()
    logger.info(f"🚀 Starting pipeline for Form {form_type}")
    logger.info(f"📄 Input PDF: {input_pdf}")
    logger.info(f"📁 Output directory: {output_root}")
    
    try:
        # Get form configuration
        config_start = time.time()
        config = get_form_config(form_type)
        logger.info(f"⚙️  Configuration loaded in {time.time() - config_start:.2f}s")
        
        # Use custom page groups if provided, otherwise use config defaults
        page_groups = custom_page_groups if custom_page_groups else config.page_groups
        logger.info(f"📑 Using {len(page_groups)} page group(s): {list(page_groups.keys())}")
        
        # Create output directory
        os.makedirs(output_root, exist_ok=True)
        
        # Split PDF into page groups
        split_start = time.time()
        subset_dir = os.path.join(output_root, "pdf_subset")
        os.makedirs(subset_dir, exist_ok=True)
        
        logger.info(f"📑 Splitting PDF into {len(page_groups)} page groups...")
        subset_paths = split_pdf_by_page_groups(
            input_pdf=input_pdf,
            page_groups=page_groups,
            output_dir=subset_dir
        )
        split_time = time.time() - split_start
        logger.info(f"✅ PDF splitting completed in {split_time:.2f}s")
        logger.info(f"   Generated {len(subset_paths)} PDF subsets")
        
        results: Dict[str, Any] = {}
        total_azure_time = 0
        total_models = 0
        
        # Process each page group
        for group_name, pdf_path in subset_paths.items():
            group_start = time.time()
            logger.info(f"📊 Processing page group: {group_name} (pages: {page_groups.get(group_name, [])})")
            
            # Try to get model from config, but allow custom groups without models
            model_config = config.model_map.get(group_name)
            if not model_config:
                logger.warning(f"⚠️  No model configuration for {group_name}, skipping analysis")
                # Still create entry in results for custom page groups
                results[group_name] = {
                    "_pages": page_groups.get(group_name, []),
                    "_pdf_path": pdf_path,
                    "_note": "No model configured for this page group"
                }
                continue
            
            # Handle both single model (1120s) and multiple models (1065/1120)
            model_ids = model_config if isinstance(model_config, list) else [model_config]
            logger.info(f"   Using {len(model_ids)} model(s): {model_ids}")
            
            if config.use_nested_models:
                # Structure for 1065/1120: nested models dict
                results[group_name] = {
                    "_pages": page_groups.get(group_name, []),
                    "_pdf_path": pdf_path,
                    "models": {}
                }
                
                for model_id in model_ids:
                    total_models += 1
                    model_start = time.time()
                    logger.info(f"   🔍 Analyzing with model: {model_id}")

                    raw_res = analyze_pdf_with_model(model_id, pdf_path)
                    
                    model_time = time.time() - model_start
                    total_azure_time += model_time
                    logger.info(f"   ✅ Model {model_id} analysis completed in {model_time:.2f}s (confidence: {raw_res.get('_confidence', 'N/A')})")

                    # Save raw individual JSON file
                    json_start = time.time()
                    safe_model = model_id.replace("/", "_").replace("\\", "_").replace(":", "_")
                    out_path = os.path.join(output_root, f"{group_name}__{safe_model}.json")
                    with open(out_path, "w", encoding="utf-8") as f:
                        json.dump(raw_res, f, ensure_ascii=False, indent=2)
                    logger.debug(f"   💾 Saved raw JSON in {time.time() - json_start:.2f}s")

                    # Apply mapping for the merged result and store it
                    mapped_res = apply_mapping_to_result(raw_res)
                    results[group_name]["models"][model_id] = mapped_res

            else:
                # Structure for 1120s: direct fields for single model, models dict for multiple models
                if len(model_ids) > 1:
                    # Multiple models: create models structure (needed for pages_13 with M1 and M2)
                    results[group_name] = {
                        "_pages": page_groups.get(group_name, []),
                        "_pdf_path": pdf_path,
                        "models": {}
                    }
                    
                    for model_id in model_ids:
                        total_models += 1
                        model_start = time.time()
                        logger.info(f"   🔍 Analyzing with model: {model_id}")

                        raw_res = analyze_pdf_with_model(model_id, pdf_path)

                        model_time = time.time() - model_start
                        total_azure_time += model_time
                        logger.info(f"   ✅ Model {model_id} analysis completed in {model_time:.2f}s (confidence: {raw_res.get('_confidence', 'N/A')})")

                        # Save raw individual JSON file
                        json_start = time.time()
                        safe_model = model_id.replace("/", "_").replace("\\", "_").replace(":", "_")
                        out_path = os.path.join(output_root, f"{group_name}__{safe_model}.json")
                        with open(out_path, "w", encoding="utf-8") as f:
                            json.dump(raw_res, f, ensure_ascii=False, indent=2)
                        logger.debug(f"   💾 Saved raw JSON in {time.time() - json_start:.2f}s")

                        # Apply mapping for the merged result and store it
                        mapped_res = apply_mapping_to_result(raw_res)
                        results[group_name]["models"][model_id] = mapped_res
                else:
                    # Single model: direct fields structure
                    model_id = model_ids[0]
                    total_models += 1
                    model_start = time.time()
                    logger.info(f"   🔍 Analyzing with model: {model_id}")

                    raw_res = analyze_pdf_with_model(model_id, pdf_path)
                    
                    # Capture metadata before normalization
                    metadata = {k: v for k, v in raw_res.items() if k.startswith('_')}

                    if for_drake:
                        raw_res = _normalize_raw_result(raw_res, model_id)
                        # Restore metadata
                        for k, v in metadata.items():
                            if k not in raw_res:
                                raw_res[k] = v
                    
                    model_time = time.time() - model_start
                    total_azure_time += model_time
                    logger.info(f"   ✅ Model {model_id} analysis completed in {model_time:.2f}s (confidence: {raw_res.get('_confidence', 'N/A')})")

                    # Save raw individual JSON file
                    json_start = time.time()
                    out_path = os.path.join(output_root, f"{group_name}.json")
                    with open(out_path, "w", encoding="utf-8") as f:
                        json.dump(raw_res, f, ensure_ascii=False, indent=2)
                    logger.debug(f"   💾 Saved raw JSON in {time.time() - json_start:.2f}s")
                    if for_drake:
                        mapped_res = map_fields_with_label_and_value(raw_res)
                    else:
                    # Apply mapping for the merged result and store it
                        mapped_res = apply_mapping_to_result(raw_res)

                    results[group_name] = mapped_res
            
            group_time = time.time() - group_start
            logger.info(f"✅ Page group {group_name} completed in {group_time:.2f}s")
        
        # Save merged JSON
        merge_start = time.time()
        merged_path = os.path.join(output_root, config.merged_json_filename)
        with open(merged_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 Merged JSON saved in {time.time() - merge_start:.2f}s")
        
        total_time = time.time() - start_time
        logger.info("=" * 60)
        logger.info(f"🎉 Pipeline completed successfully!")
        logger.info(f"⏱️  Total time: {total_time:.2f}s ({total_time/60:.2f} minutes)")
        logger.info(f"   - PDF splitting: {split_time:.2f}s ({split_time/total_time*100:.1f}%)")
        logger.info(f"   - Azure analysis: {total_azure_time:.2f}s ({total_azure_time/total_time*100:.1f}%) - {total_models} models, avg: {total_azure_time/total_models if total_models > 0 else 0:.2f}s/model")
        other_time = total_time - split_time - total_azure_time
        logger.info(f"   - Other operations: {other_time:.2f}s ({other_time/total_time*100:.1f}%)")
        logger.info("=" * 60)
        
        results["_execution_stats"] = {
            "total_time": total_time,
            "split_time": split_time,
            "azure_analysis_time": total_azure_time,
            "total_models": total_models
        }
        
        return results
        
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(f"❌ Pipeline failed after {total_time:.2f}s")
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise
