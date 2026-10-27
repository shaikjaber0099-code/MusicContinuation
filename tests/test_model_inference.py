"""
Tests for model loading, conditioned generation, input preservation, and performance.
Covers TC-04, TC-05, TC-06, TC-07, TC-11, TC-15.
"""
import os
import copy
import pytest
from generation.generator import MusicGenerator
from output.validator import validate_generated_events
from input.note_parser import parse_melody_string

WEIGHTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "weights"))

def test_tc04_model_missing_error():
    """TC-04: If model weights are missing, generation is blocked with setup-oriented message."""
    non_existent_dir = os.path.join(os.path.dirname(__file__), "fake_model_dir")
    gen = MusicGenerator(model_dir=non_existent_dir)
    status = gen.check_availability()
    assert status['available'] is False
    assert "Model artifacts not found" in status['error']

    with pytest.raises(RuntimeError) as exc_info:
        gen.generate([{'pitch': 'C4', 'midi': 60, 'duration': 1.0, 'is_rest': False}], num_events=8)
    assert "The music model is not available right now" in str(exc_info.value)

def test_tc05_valid_generation():
    """TC-05: Valid input produces the requested number of continuation events."""
    gen = MusicGenerator(model_dir=WEIGHTS_DIR)
    assert gen.is_loaded is True

    prompt = parse_melody_string("C4 D4 E4 G4")
    result = gen.generate(input_events=prompt, num_events=16, temperature=0.8)

    assert result['continuation_count'] == 16
    assert result['original_count'] == 4
    assert result['total_count'] == 20
    assert len(result['continuation_events']) == 16

def test_tc06_input_preservation():
    """TC-06: The original melody is untouched and perfectly preserved."""
    gen = MusicGenerator(model_dir=WEIGHTS_DIR)
    prompt = parse_melody_string("C4:1.0 D4:0.5 E4:0.5 G4:2.0")
    original_copy = copy.deepcopy(prompt)

    result = gen.generate(input_events=prompt, num_events=12)

    # Assert original input list in caller memory was not modified
    assert prompt == original_copy

    # Assert returned original events match input values
    for orig, res_orig in zip(original_copy, result['original_events']):
        assert orig['pitch'] == res_orig['pitch']
        assert orig['midi'] == res_orig['midi']
        assert orig['duration'] == res_orig['duration']
        assert res_orig['source'] == 'original'

def test_tc07_output_integrity():
    """TC-07: Generated events decode properly and pass structural validation."""
    gen = MusicGenerator(model_dir=WEIGHTS_DIR)
    prompt = parse_melody_string("E4 F#4 G4 B4")
    result = gen.generate(input_events=prompt, num_events=16)

    val_res = validate_generated_events(result['continuation_events'])
    assert val_res['valid'] is True
    assert val_res['count'] == 16

    # Verify each event has valid pitch / duration
    for ev in result['continuation_events']:
        assert 'duration' in ev
        assert ev['duration'] > 0
        if not ev.get('is_rest', False):
            assert 0 <= ev['midi'] <= 127
            assert len(ev['pitch']) >= 2

def test_tc11_regenerate_replaces_continuation():
    """TC-11: Regenerating produces a new continuation rather than appending to old."""
    gen = MusicGenerator(model_dir=WEIGHTS_DIR)
    prompt = parse_melody_string("C4 E4 G4")

    run_1 = gen.generate(input_events=prompt, num_events=8, temperature=0.5)
    run_2 = gen.generate(input_events=prompt, num_events=8, temperature=1.2)

    # Both must have exactly 8 continuation events
    assert len(run_1['continuation_events']) == 8
    assert len(run_2['continuation_events']) == 8

    # Original sequence must be exactly the 3 prompt notes in both
    assert run_1['original_count'] == 3
    assert run_2['original_count'] == 3

def test_tc15_performance_under_10_seconds():
    """TC-15: Continuation is generated well within the 10-second requirement."""
    gen = MusicGenerator(model_dir=WEIGHTS_DIR)
    prompt = parse_melody_string("C4 D4 E4 F4 G4 A4 B4 C5")

    result = gen.generate(input_events=prompt, num_events=32)
    assert result['generation_time_seconds'] < 10.0
    print(f"Generation time for 32 notes: {result['generation_time_seconds']}s")
