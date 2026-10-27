"""
Unit tests for input validation (TC-01, TC-02, TC-03).
"""
import pytest
from input.validator import validate_text_melody, validate_midi_file, validate_melody_events
from input.note_parser import parse_melody_string, note_name_to_midi, midi_to_note_name

def test_tc01_valid_melody_text():
    """TC-01: Valid melody input is accepted and parsed."""
    result = validate_text_melody("C4 D4 E4 G4 A4")
    assert result['valid'] is True
    assert result['count'] == 5
    assert result['pitched_count'] == 5
    assert "C4" in result['preview_str']
    assert result['source'] == 'manual'

def test_tc01_valid_melody_with_durations_and_rests():
    """TC-01: Valid melody with durations and rests."""
    result = validate_text_melody("C4:1.0 D4:0.5 REST:0.5 E4:2.0")
    assert result['valid'] is True
    assert result['count'] == 4
    assert result['pitched_count'] == 3
    assert result['total_beats'] == 4.0

def test_tc02_empty_input_blocked():
    """TC-02: Empty input is rejected with actionable message."""
    res_empty = validate_text_melody("")
    assert res_empty['valid'] is False
    assert res_empty['error_code'] == 'EMPTY_INPUT'
    assert "Add a few notes" in res_empty['error']

    res_whitespace = validate_text_melody("    ")
    assert res_whitespace['valid'] is False
    assert res_whitespace['error_code'] == 'EMPTY_INPUT'

def test_tc02_invalid_notes_rejected():
    """TC-02: Invalid note names produce actionable guidance."""
    result = validate_text_melody("H4 Z9")
    assert result['valid'] is False
    assert result['error_code'] == 'INVALID_MELODY'
    assert "Invalid note pitch format" in result['error']

def test_tc02_only_rests_rejected():
    """TC-02: Melody consisting solely of rests is rejected."""
    result = validate_text_melody("REST:1.0 REST:2.0")
    assert result['valid'] is False
    assert result['error_code'] == 'ONLY_RESTS'

def test_tc03_unsupported_file_extension():
    """TC-03: Unsupported file types are safely rejected."""
    result = validate_midi_file(b"some audio data", "melody.wav")
    assert result['valid'] is False
    assert result['error_code'] == 'UNSUPPORTED_FILE'
    assert "not supported" in result['error']

def test_tc03_corrupt_midi_bytes():
    """TC-03: Corrupt or truncated MIDI files are safely rejected without crash."""
    result = validate_midi_file(b"NOT_A_VALID_MIDI_HEADER", "test.mid")
    assert result['valid'] is False
    assert result['error_code'] == 'INVALID_MELODY'
    assert "Corrupt or non-MIDI" in result['error']

def test_tc03_empty_midi_file():
    """TC-03: Empty MIDI file is rejected safely."""
    result = validate_midi_file(b"", "empty.mid")
    assert result['valid'] is False
    assert result['error_code'] == 'EMPTY_INPUT'
