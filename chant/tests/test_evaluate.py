"""Tests for chant.evaluate — EvaluationReport construction and aggregation.

All tests use synthetic data; the real model is never loaded.
"""

from __future__ import annotations

import pytest

from chant.evaluate import EvaluationReport, _report_to_dict


# ---------------------------------------------------------------------------
# EvaluationReport construction
# ---------------------------------------------------------------------------

def _make_report(**overrides) -> EvaluationReport:
    """Return a minimal EvaluationReport with sensible defaults."""
    defaults = dict(
        num_samples=10,
        num_valid=7,
        pass_rate=0.7,
        avg_events=15.0,
        avg_generation_time_s=2.5,
        pitch_range=(110.0, 880.0),
        channel_distribution={0: 50, 1: 30, 2: 20},
        failure_reasons={"sequence is empty": 2, "unparseable token string": 1},
        avg_metrics={"pitch_entropy": 2.5, "rhythm_regularity": 0.3, "channel_balance": 0.8, "repetition_score": 0.1},
        per_sample=[],
    )
    defaults.update(overrides)
    return EvaluationReport(**defaults)


class TestEvaluationReportConstruction:
    def test_fields_assigned(self):
        r = _make_report()
        assert r.num_samples == 10
        assert r.num_valid == 7
        assert r.pass_rate == 0.7
        assert r.avg_events == 15.0
        assert r.avg_generation_time_s == 2.5
        assert r.pitch_range == (110.0, 880.0)
        assert r.channel_distribution == {0: 50, 1: 30, 2: 20}

    def test_pitch_range_none_allowed(self):
        r = _make_report(pitch_range=None)
        assert r.pitch_range is None

    def test_empty_dicts_allowed(self):
        r = _make_report(
            channel_distribution={},
            failure_reasons={},
            per_sample=[],
        )
        assert r.channel_distribution == {}
        assert r.failure_reasons == {}
        assert r.per_sample == []


# ---------------------------------------------------------------------------
# pass_rate calculation
# ---------------------------------------------------------------------------

class TestPassRate:
    def test_all_pass(self):
        r = _make_report(num_samples=5, num_valid=5, pass_rate=5 / 5)
        assert r.pass_rate == 1.0

    def test_all_fail(self):
        r = _make_report(num_samples=5, num_valid=0, pass_rate=0.0)
        assert r.pass_rate == 0.0

    def test_partial(self):
        r = _make_report(num_samples=10, num_valid=3, pass_rate=3 / 10)
        assert r.pass_rate == pytest.approx(0.3)

    def test_pass_rate_matches_counts(self):
        r = _make_report(num_samples=20, num_valid=14, pass_rate=14 / 20)
        assert r.pass_rate == pytest.approx(r.num_valid / r.num_samples)


# ---------------------------------------------------------------------------
# failure_reasons aggregation
# ---------------------------------------------------------------------------

class TestFailureReasons:
    def test_single_reason(self):
        r = _make_report(failure_reasons={"sequence is empty": 3})
        assert r.failure_reasons["sequence is empty"] == 3

    def test_multiple_reasons(self):
        reasons = {
            "sequence is empty": 2,
            "unparseable token string": 1,
            "pitch 15.00 Hz is below minimum 20 Hz": 1,
        }
        r = _make_report(failure_reasons=reasons)
        assert len(r.failure_reasons) == 3
        assert r.failure_reasons["unparseable token string"] == 1

    def test_no_failures(self):
        r = _make_report(num_valid=10, failure_reasons={})
        assert r.failure_reasons == {}

    def test_total_failures_consistent(self):
        """num_valid + sum of failure counts should equal num_samples."""
        reasons = {"sequence is empty": 2, "unparseable token string": 1}
        r = _make_report(num_samples=10, num_valid=7, failure_reasons=reasons)
        total_failures = sum(r.failure_reasons.values())
        assert r.num_valid + total_failures == r.num_samples


# ---------------------------------------------------------------------------
# channel_distribution aggregation
# ---------------------------------------------------------------------------

class TestChannelDistribution:
    def test_single_channel(self):
        r = _make_report(channel_distribution={0: 100})
        assert r.channel_distribution[0] == 100

    def test_multi_channel(self):
        dist = {0: 40, 1: 30, 2: 20, 3: 10}
        r = _make_report(channel_distribution=dist)
        assert sum(r.channel_distribution.values()) == 100
        assert r.channel_distribution[3] == 10

    def test_empty_distribution(self):
        r = _make_report(channel_distribution={})
        assert r.channel_distribution == {}

    def test_channel_keys_are_ints(self):
        dist = {0: 5, 1: 5}
        r = _make_report(channel_distribution=dist)
        for key in r.channel_distribution:
            assert isinstance(key, int)


# ---------------------------------------------------------------------------
# _report_to_dict serialisation
# ---------------------------------------------------------------------------

class TestReportToDict:
    def test_pitch_range_becomes_list(self):
        r = _make_report(pitch_range=(110.0, 880.0))
        d = _report_to_dict(r)
        assert isinstance(d["pitch_range"], list)
        assert d["pitch_range"] == [110.0, 880.0]

    def test_pitch_range_none_preserved(self):
        r = _make_report(pitch_range=None)
        d = _report_to_dict(r)
        assert d["pitch_range"] is None

    def test_channel_keys_become_strings(self):
        r = _make_report(channel_distribution={0: 10, 1: 5})
        d = _report_to_dict(r)
        for key in d["channel_distribution"]:
            assert isinstance(key, str)

    def test_all_top_level_fields_present(self):
        r = _make_report()
        d = _report_to_dict(r)
        expected_keys = {
            "num_samples", "num_valid", "pass_rate", "avg_events",
            "avg_generation_time_s", "pitch_range", "channel_distribution",
            "failure_reasons", "per_sample",
        }
        assert expected_keys.issubset(d.keys())
