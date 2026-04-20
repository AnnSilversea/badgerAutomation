"""Shared fixtures for the rating-system test suite.

The rating functions in AI_Page.di_client operate on lists of page dicts
shaped as {"page_number": int, "text": str, "source": str}. These fixtures
produce reusable page bundles covering the important regimes:

- empty / near-empty pages (below the 30-char cutoff)
- dense pages (well above thresholds)
- tax-signal pages (contain the keywords the heuristic looks for)
"""
from __future__ import annotations

from typing import Callable, List, Dict, Any

import pytest


Page = Dict[str, Any]
PageFactory = Callable[..., Page]


@pytest.fixture
def make_page() -> PageFactory:
    def _make(page_number: int = 1, text: str = "", source: str = "pymupdf") -> Page:
        return {"page_number": page_number, "text": text, "source": source}
    return _make


@pytest.fixture
def empty_page(make_page: PageFactory) -> Page:
    return make_page(text="")


@pytest.fixture
def nearly_empty_page(make_page: PageFactory) -> Page:
    # 29 chars: below the 30-char empty-page cutoff
    return make_page(text="x" * 29)


@pytest.fixture
def short_page(make_page: PageFactory) -> Page:
    # 30 chars exactly: the first non-empty page
    return make_page(text="x" * 30)


@pytest.fixture
def dense_page(make_page: PageFactory) -> Page:
    return make_page(text="x" * 2000)


@pytest.fixture
def tax_signal_page(make_page: PageFactory) -> Page:
    return make_page(text="U.S. Income Tax Return Form 1120-S " + ("x" * 500))


@pytest.fixture
def pages_all_empty(make_page: PageFactory) -> List[Page]:
    return [make_page(page_number=i + 1, text="") for i in range(5)]


@pytest.fixture
def pages_dense_no_signals(make_page: PageFactory) -> List[Page]:
    # 5 pages * 2000 chars = 10,000 chars; no tax keywords
    return [make_page(page_number=i + 1, text="lorem ipsum " * 200) for i in range(5)]


@pytest.fixture
def pages_dense_with_signals(make_page: PageFactory) -> List[Page]:
    pages = [make_page(page_number=i + 1, text="lorem ipsum " * 200) for i in range(4)]
    pages.append(make_page(page_number=5, text="Schedule L balance sheets per books " + ("x" * 500)))
    return pages
