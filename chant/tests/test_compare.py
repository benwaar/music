"""Tests for chant/compare.py — conditioned vs unconditioned comparison.

All tests use synthetic/mock data — no real model is loaded.
"""

from __future__ import annotations

from chant.compare import (
    ComparisonReport,
    DIVERSITY_METRICS,
    _count_wins,
    _make_diversity_comparison,
    _make_summary,
)


# ---------------------------------------------------------------------------
# ComparisonReport construction
# ---------------------------------------------------------------------------


class TestComparisonReport:
    def test_dataclass_construction_defaults(self):
        report = ComparisonReport(
            num_samples=10,
            conditioned_valid=8,
            unconditioned_valid=5,
            conditioned_avg_events=32.5,
            unconditioned_avg_events=18.0,
        )
        assert report.num_samples == 10
        assert report.conditioned_valid == 8
        assert report.unconditioned_valid == 5
        assert report.conditioned_avg_events == 32.5
        assert report.unconditioned_avg_events == 18.0
        assert report.diversity_comparison == {}
        assert report.conditioned_wins == {}
        assert report.summary == ""

    def test_dataclass_construction_full(self):
        report = ComparisonReport(
            num_samples=5,
            conditioned_valid=4,
            unconditioned_valid=3,
            conditioned_avg_events=20.0,
            unconditioned_avg_events=15.0,
            diversity_comparison={"pitch_diversity_conditioned": 7.0},
            conditioned_wins={"pitch_diversity": 3},
            summary="Conditioning helps: conditioned wins 15/15 metric-samples (100%).",
        )
        assert report.diversity_comparison == {"pitch_diversity_conditioned": 7.0}
        assert report.conditioned_wins == {"pitch_diversity": 3}
        assert "Conditioning helps" in report.summary

    def test_zero_samples(self):
        report = ComparisonReport(
            num_samples=0,
            conditioned_valid=0,
            unconditioned_valid=0,
            conditioned_avg_events=0.0,
            unconditioned_avg_events=0.0,
        )
        assert report.num_samples == 0


# ---------------------------------------------------------------------------
# _count_wins
# ---------------------------------------------------------------------------


class TestCountWins:
    def _sample(self, pd_c, pd_u, dd_c, dd_u, cs_c, cs_u) -> dict:
        return {
            "pitch_diversity_conditioned": pd_c,
            "pitch_diversity_unconditioned": pd_u,
            "duration_diversity_conditioned": dd_c,
            "duration_diversity_unconditioned": dd_u,
            "channel_spread_conditioned": cs_c,
            "channel_spread_unconditioned": cs_u,
        }

    def test_all_wins(self):
        samples = [self._sample(5, 2, 4, 1, 3, 1)]
        wins = _count_wins(samples)
        assert wins["pitch_diversity"] == 1
        assert wins["duration_diversity"] == 1
        assert wins["channel_spread"] == 1

    def test_no_wins(self):
        samples = [self._sample(2, 5, 1, 4, 1, 3)]
        wins = _count_wins(samples)
        assert wins["pitch_diversity"] == 0
        assert wins["duration_diversity"] == 0
        assert wins["channel_spread"] == 0

    def test_tie_does_not_count_as_win(self):
        samples = [self._sample(3, 3, 3, 3, 3, 3)]
        wins = _count_wins(samples)
        for m in DIVERSITY_METRICS:
            assert wins[m] == 0

    def test_multiple_samples_mixed(self):
        # Sample 1: cond wins pitch, ties duration, loses channel
        # Sample 2: cond wins all
        s1 = self._sample(5, 2, 3, 3, 1, 4)
        s2 = self._sample(6, 3, 5, 2, 4, 2)
        wins = _count_wins([s1, s2])
        assert wins["pitch_diversity"] == 2    # wins both
        assert wins["duration_diversity"] == 1  # wins only sample 2
        assert wins["channel_spread"] == 1      # wins only sample 2

    def test_empty_samples(self):
        wins = _count_wins([])
        for m in DIVERSITY_METRICS:
            assert wins[m] == 0


# ---------------------------------------------------------------------------
# _make_diversity_comparison
# ---------------------------------------------------------------------------


class TestMakeDiversityComparison:
    def _sample(self, pd_c, pd_u, dd_c, dd_u, cs_c, cs_u) -> dict:
        return {
            "pitch_diversity_conditioned": pd_c,
            "pitch_diversity_unconditioned": pd_u,
            "duration_diversity_conditioned": dd_c,
            "duration_diversity_unconditioned": dd_u,
            "channel_spread_conditioned": cs_c,
            "channel_spread_unconditioned": cs_u,
        }

    def test_averages_single_sample(self):
        samples = [self._sample(4, 2, 6, 3, 2, 1)]
        result = _make_diversity_comparison(samples)
        assert result["pitch_diversity_conditioned"] == 4.0
        assert result["pitch_diversity_unconditioned"] == 2.0
        assert result["duration_diversity_conditioned"] == 6.0
        assert result["duration_diversity_unconditioned"] == 3.0
        assert result["channel_spread_conditioned"] == 2.0
        assert result["channel_spread_unconditioned"] == 1.0

    def test_averages_two_samples(self):
        s1 = self._sample(4, 2, 6, 2, 2, 1)
        s2 = self._sample(6, 4, 2, 4, 4, 3)
        result = _make_diversity_comparison([s1, s2])
        assert result["pitch_diversity_conditioned"] == 5.0
        assert result["pitch_diversity_unconditioned"] == 3.0
        assert result["channel_spread_conditioned"] == 3.0
        assert result["channel_spread_unconditioned"] == 2.0

    def test_empty_returns_empty_dict(self):
        assert _make_diversity_comparison([]) == {}


# ---------------------------------------------------------------------------
# _make_summary
# ---------------------------------------------------------------------------


class TestMakeSummary:
    def _wins_all(self, n: int) -> dict[str, int]:
        """Conditioned wins all samples for all metrics."""
        return {m: n for m in DIVERSITY_METRICS}

    def _wins_none(self) -> dict[str, int]:
        return {m: 0 for m in DIVERSITY_METRICS}

    def test_no_samples(self):
        summary = _make_summary(self._wins_none(), 0)
        assert "No samples" in summary

    def test_conditioning_helps_when_majority_wins(self):
        # 10 samples, wins all metrics for all samples
        summary = _make_summary(self._wins_all(10), 10)
        assert "Conditioning helps" in summary

    def test_no_clear_benefit_when_no_wins(self):
        summary = _make_summary(self._wins_none(), 10)
        assert "No clear benefit" in summary

    def test_conditioning_helps_when_two_of_three_metrics_dominant(self):
        wins = {
            "pitch_diversity": 8,     # > 50% of 10 → dominant
            "duration_diversity": 7,  # > 50% of 10 → dominant
            "channel_spread": 2,      # < 50% → not dominant
        }
        summary = _make_summary(wins, 10)
        assert "Conditioning helps" in summary

    def test_no_clear_benefit_when_one_metric_dominant(self):
        wins = {
            "pitch_diversity": 9,
            "duration_diversity": 2,
            "channel_spread": 2,
        }
        summary = _make_summary(wins, 10)
        assert "No clear benefit" in summary

    def test_summary_contains_ratio(self):
        wins = self._wins_all(10)
        summary = _make_summary(wins, 10)
        # Total wins = 30 out of 30 total possible metric-samples
        assert "30/30" in summary
