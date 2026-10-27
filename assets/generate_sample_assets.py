"""
Generates sample MIDI files and corrupt/invalid test assets in assets/sample_melodies/
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from input.note_parser import parse_melody_string
from output.midi_writer import save_events_to_midi_file

def create_sample_assets():
    assets_dir = os.path.join(os.path.dirname(__file__), "sample_melodies")
    os.makedirs(assets_dir, exist_ok=True)

    samples = {
        "ode_to_joy.mid": "E4:1.0 E4:1.0 F4:1.0 G4:1.0 G4:1.0 F4:1.0 E4:1.0 D4:1.0 C4:1.0 C4:1.0 D4:1.0 E4:1.0 E4:1.5 D4:0.5 D4:2.0",
        "twinkle.mid": "C4:1.0 C4:1.0 G4:1.0 G4:1.0 A4:1.0 A4:1.0 G4:2.0 F4:1.0 F4:1.0 E4:1.0 E4:1.0 D4:1.0 D4:1.0 C4:2.0",
        "scale_c_major.mid": "C4:1.0 D4:1.0 E4:1.0 F4:1.0 G4:1.0 A4:1.0 B4:1.0 C5:2.0",
        "greensleeves.mid": "E4:1.0 G4:1.5 A4:0.5 B4:1.0 C5:0.5 B4:0.5 A4:1.0 F#4:1.5 D4:0.5 E4:0.5 F#4:0.5 G4:1.0 E4:2.0"
    }

    for filename, melody_str in samples.items():
        filepath = os.path.join(assets_dir, filename)
        events = parse_melody_string(melody_str)
        save_events_to_midi_file(events, filepath, bpm=120, track_name=filename.replace('.mid', ''))
        print(f"Generated sample MIDI: {filepath}")

    # Generate an invalid/corrupt MIDI file for testing TC-03
    corrupt_path = os.path.join(assets_dir, "corrupt_file.mid")
    with open(corrupt_path, "wb") as f:
        f.write(b"NOT_A_MIDI_FILE_JUST_RANDOM_TEXT_DATA_FOR_ERROR_TESTING")
    print(f"Generated corrupt test asset: {corrupt_path}")

    # Generate an empty MIDI file
    empty_path = os.path.join(assets_dir, "empty_file.mid")
    with open(empty_path, "wb") as f:
        f.write(b"")
    print(f"Generated empty test asset: {empty_path}")

if __name__ == "__main__":
    create_sample_assets()
