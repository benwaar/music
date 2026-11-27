"""Tests for chant/generate.py — _fixup_events."""

from __future__ import annotations

import pytest

from chant.generate import _fixup_events
from chant.schema import NoteEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _event(channel: int, pitch_hz: float = 440.0, duration_ms: float = 100.0) -> NoteEvent:
    return NoteEvent(pitch_hz=pitch_hz, duration_ms=duration_ms, channel=channel)


# ---------------------------------------------------------------------------
# Channel boundary cases
# ---------------------------------------------------------------------------

def test_channel_zero_stays():
    events = _fixup_events([_event(0)])
    assert events[0].channel == 0


def test_channel_max_stays():
    events = _fixup_events([_event(31)])
    assert events[0].channel == 31


def test_channel_32_wraps_to_0():
    events = _fixup_events([_event(32)])
    assert events[0].channel == 0


def test_channel_33_wraps_to_1():
    events = _fixup_events([_event(33)])
    assert events[0].channel == 1


def test_channel_negative_1_wraps_to_31():
    events = _fixup_events([_event(-1)])
    assert events[0].channel == 31


# ---------------------------------------------------------------------------
# Valid channels are untouched — pitch and duration preserved
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ch", [0, 1, 15, 30, 31])
def test_valid_channels_untouched(ch: int):
    events = _fixup_events([_event(ch, pitch_hz=880.0, duration_ms=250.0)])
    assert events[0].channel == ch
    assert events[0].pitch_hz == 880.0
    assert events[0].duration_ms == 250.0


# ---------------------------------------------------------------------------
# Empty list
# ---------------------------------------------------------------------------

def test_empty_list_returns_empty():
    assert _fixup_events([]) == []


# ---------------------------------------------------------------------------
# Mixed valid and invalid in one list
# ---------------------------------------------------------------------------

def test_mixed_channels():
    events = _fixup_events([
        _event(0),    # valid — stays 0
        _event(31),   # valid — stays 31
        _event(32),   # wraps to 0
        _event(-1),   # wraps to 31
        _event(10),   # valid — stays 10
        _event(64),   # 64 % 32 = 0
    ])
    assert [e.channel for e in events] == [0, 31, 0, 31, 10, 0]
