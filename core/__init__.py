"""
Core module for Badger Automation
Unified pipeline for processing tax documents
"""

from .pipeline import run_pipeline
from .config import FormConfig, get_form_config

__all__ = ['run_pipeline', 'FormConfig', 'get_form_config']

