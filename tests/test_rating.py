"""Unit tests for AI_Page.di_client rating heuristics.

Targets three pure functions:
    _score_text_quality(pages)       -> metrics dict
    should_use_di_full(pages)        -> bool
    pages_need_di_subset(pages, cutoff=30) -> list[int]

The thresholds under test (all from di_client.py):
    total_chars  < 1200   -> DI full
    empty_ratio  >= 0.60  -> DI full
    (no signals) & total_chars < 6000 -> DI full
    empty page cutoff     = 30 chars
"""
from __future__ import annotations

from typing import List, Dict, Any

import pytest

from AI_Page.di_client import (
    _score_text_quality,
    should_use_di_full,
    pages_need_di_subset,
)


# ---------------------------------------------------------------------------
# _score_text_quality
# ---------------------------------------------------------------------------
class TestScoreTextQuality:
    def test_empty_page_list_does_not_divide_by_zero(self):
        m = _score_text_quality([])
        assert m["total_chars"] == 0
        assert m["empty_pages"] == 0
        assert m["page_count"] == 1  # max(1, 0)
        assert m["empty_ratio"] == 0.0
        assert m["has_tax_signals"] is False

    def test_single_empty_page(self, empty_page):
        m = _score_text_quality([empty_page])
        assert m["total_chars"] == 0
        assert m["empty_pages"] == 1
        assert m["page_count"] == 1
        assert m["empty_ratio"] == 1.0

    @pytest.mark.parametrize(
        "char_count,expected_empty",
        [
            (0, 1),
            (1, 1),
            (29, 1),   # just below cutoff
            (30, 0),   # exactly at cutoff -> NOT empty (strict <)
            (31, 0),
            (1000, 0),
        ],
    )
    def test_empty_page_cutoff_is_strict_less_than_30(self, make_page, char_count, expected_empty):
        pages = [make_page(text="x" * char_count)]
        m = _score_text_quality(pages)
        assert m["empty_pages"] == expected_empty
        assert m["total_chars"] == char_count

    def test_empty_ratio_is_fraction_of_empty_pages(self, make_page):
        pages = [make_page(page_number=i + 1, text="x" * (0 if i < 3 else 100)) for i in range(5)]
        m = _score_text_quality(pages)
        assert m["empty_pages"] == 3
        assert m["page_count"] == 5
        assert m["empty_ratio"] == pytest.approx(0.6)

    @pytest.mark.parametrize(
        "signal_text",
        [
            "Form 1120-S",
            "form 1120-s",
            "FORM 1120-S",
            "Schedule L",
            "schedule m-1",
            "Schedule M-2",
            "Balance Sheets Per Books",
            "U.S. Income Tax Return",
        ],
    )
    def test_tax_signals_detected_case_insensitive(self, make_page, signal_text):
        pages = [make_page(text=signal_text + " " + "x" * 100)]
        m = _score_text_quality(pages)
        assert m["has_tax_signals"] is True

    def test_no_tax_signals_in_generic_text(self, make_page):
        pages = [make_page(text="lorem ipsum dolor sit amet " * 50)]
        m = _score_text_quality(pages)
        assert m["has_tax_signals"] is False

    def test_signals_detected_across_page_boundary(self, make_page):
        # Signals are detected on concatenated lowercased text; split across pages still counts.
        pages = [
            make_page(page_number=1, text="Schedule"),
            make_page(page_number=2, text="L per books"),
        ]
        # "schedule l" appears once the texts are joined with a space
        m = _score_text_quality(pages)
        assert m["has_tax_signals"] is True

    def test_total_chars_sums_all_pages(self, make_page):
        pages = [make_page(page_number=i + 1, text="x" * n) for i, n in enumerate([10, 20, 30])]
        m = _score_text_quality(pages)
        assert m["total_chars"] == 60


# ---------------------------------------------------------------------------
# should_use_di_full
# ---------------------------------------------------------------------------
class TestShouldUseDiFull:
    def test_all_empty_pages_trigger_di_full(self, pages_all_empty):
        assert should_use_di_full(pages_all_empty) is True

    def test_dense_text_without_signals_under_6000_triggers_di(self, make_page):
        # 5 pages * ~200 chars = 1000 chars; < 1200 -> True by the total_chars rule
        pages = [make_page(page_number=i + 1, text="lorem ipsum " * 20) for i in range(5)]
        assert should_use_di_full(pages) is True

    def test_dense_text_without_signals_over_6000_passes(self, pages_dense_no_signals):
        # 5 pages * ("lorem ipsum " * 200) = 5 * 2400 = 12_000 chars, no signals, no empties.
        m = _score_text_quality(pages_dense_no_signals)
        assert m["total_chars"] >= 6000
        assert m["has_tax_signals"] is False
        assert m["empty_ratio"] < 0.6
        assert should_use_di_full(pages_dense_no_signals) is False

    def test_dense_with_signals_between_1200_and_6000_passes(self, pages_dense_with_signals):
        # Signals present -> the <6000 no-signal rule does not apply.
        m = _score_text_quality(pages_dense_with_signals)
        assert m["has_tax_signals"] is True
        assert m["total_chars"] >= 1200
        assert m["empty_ratio"] < 0.6
        assert should_use_di_full(pages_dense_with_signals) is False

    @pytest.mark.parametrize(
        "empty_count,total_pages,expected",
        [
            (2, 5, False),   # ratio 0.4
            (3, 5, True),    # ratio 0.6 exactly -> True
            (4, 5, True),    # ratio 0.8
        ],
    )
    def test_empty_ratio_threshold_is_inclusive_at_0_60(
        self, make_page, empty_count, total_pages, expected
    ):
        # Each non-empty page is dense + has signals so the other rules don't fire.
        pages: List[Dict[str, Any]] = []
        for i in range(total_pages):
            if i < empty_count:
                pages.append(make_page(page_number=i + 1, text=""))
            else:
                pages.append(
                    make_page(
                        page_number=i + 1,
                        text="Form 1120-S Schedule L " + "x" * 3000,
                    )
                )
        assert should_use_di_full(pages) is expected

    def test_just_under_1200_chars_triggers_di(self, make_page):
        # 1199 chars, on a single dense page with signals to isolate the total_chars rule.
        pages = [make_page(text="Form 1120-S " + "x" * (1199 - len("Form 1120-S ")))]
        assert _score_text_quality(pages)["total_chars"] == 1199
        assert should_use_di_full(pages) is True

    def test_exactly_1200_chars_with_signals_passes(self, make_page):
        prefix = "Form 1120-S "
        pages = [make_page(text=prefix + "x" * (1200 - len(prefix)))]
        m = _score_text_quality(pages)
        assert m["total_chars"] == 1200
        assert m["has_tax_signals"] is True
        assert should_use_di_full(pages) is False


# ---------------------------------------------------------------------------
# pages_need_di_subset
# ---------------------------------------------------------------------------
class TestPagesNeedDiSubset:
    def test_returns_empty_when_all_pages_dense(self, pages_dense_no_signals):
        assert pages_need_di_subset(pages_dense_no_signals) == []

    def test_returns_all_page_numbers_when_all_empty(self, pages_all_empty):
        assert pages_need_di_subset(pages_all_empty) == [1, 2, 3, 4, 5]

    def test_preserves_1_based_page_numbers_not_indices(self, make_page):
        pages = [
            make_page(page_number=3, text=""),           # empty
            make_page(page_number=7, text="x" * 100),    # ok
            make_page(page_number=11, text="x" * 10),    # empty
        ]
        assert pages_need_di_subset(pages) == [3, 11]

    def test_default_cutoff_is_30_chars(self, make_page):
        pages = [
            make_page(page_number=1, text="x" * 29),  # below cutoff
            make_page(page_number=2, text="x" * 30),  # at cutoff -> NOT included
        ]
        assert pages_need_di_subset(pages) == [1]

    @pytest.mark.parametrize("cutoff", [10, 50, 100, 500])
    def test_custom_cutoff_is_honored(self, make_page, cutoff):
        pages = [
            make_page(page_number=1, text="x" * (cutoff - 1)),
            make_page(page_number=2, text="x" * cutoff),
            make_page(page_number=3, text="x" * (cutoff + 1)),
        ]
        assert pages_need_di_subset(pages, empty_page_chars=cutoff) == [1]

    def test_empty_input_returns_empty_list(self):
        assert pages_need_di_subset([]) == []
