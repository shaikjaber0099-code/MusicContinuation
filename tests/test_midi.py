"""
Tests for MIDI parsing and export (TC-03, TC-10).
"""
import os
import io
import mido
import pytest
from input.midi_parser import parse_midi_bytes
from output.midi_writer import events_to_midi_bytes
from input.note_parser import parse_melody_string

ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "sample_melodies"))

def test_parse_valid_sample_midi():
    """Tests parsing of created sample MIDI files."""
    sample_file = os.path.join(ASSETS_DIR, "ode_to_joy.mid")
    assert os.path.exists(sample_file)

    with open(sample_file, "rb") as f:
        file_bytes = f.read()

    events = parse_midi_bytes(file_bytes, "ode_to_joy.mid")
    assert len(events) > 0
    assert events[0]['pitch'] == 'E4'
    assert events[0]['midi'] == 64

def test_parse_corrupt_midi():
    """TC-03: Corrupt MIDI is safely rejected with descriptive error."""
    corrupt_file = os.path.join(ASSETS_DIR, "corrupt_file.mid")
    with open(corrupt_file, "rb") as f:
        corrupt_bytes = f.read()

    with pytest.raises(ValueError) as exc:
        parse_midi_bytes(corrupt_bytes, "corrupt_file.mid")
    assert "Corrupt or non-MIDI file" in str(exc.value)

def test_tc10_midi_export():
    """TC-10: Exported MIDI file is valid, opens in mido, and contains both sections."""
    melody = parse_melody_string("C4:1.0 D4:1.0 E4:1.0 G4:1.0")
    continuation = parse_melody_string("A4:1.0 G4:1.0 E4:1.0 D4:1.0")

    combined = []
    for ev in melody:
        c = dict(ev)
        c['source'] = 'original'
        combined.append(c)
    for ev in continuation:
        c = dict(ev)
        c['source'] = 'continuation'
        combined.append(c)

    # Export to MIDI bytes
    midi_bytes = events_to_midi_bytes(combined, bpm=120)
    assert len(midi_bytes) > 0
    assert midi_bytes.startswith(b'MThd')

    # Read back with mido to verify integrity
    mid_obj = mido.MidiFile(file=io.BytesIO(midi_bytes))
    assert len(mid_obj.tracks) > 0

    # Collect note_on events
    note_ons = []
    for track in mid_obj.tracks:
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                note_ons.append(msg.note)

    # Expected: C4(60), D4(62), E4(64), G4(67), A4(69), G4(67), E4(64), D4(62)
    expected_notes = [60, 62, 64, 67, 69, 67, 64, 62]
    assert note_ons == expected_notes
