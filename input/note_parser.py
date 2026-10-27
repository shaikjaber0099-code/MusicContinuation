"""
Note parser module for symbolic melody representations.
Parses scientific pitch notation with optional duration and rests.
"""
from typing import List, Dict, Any, Optional, Tuple
import re

NOTE_NAME_TO_SEMITONE = {
    'C': 0, 'B#': 0,
    'C#': 1, 'DB': 1,
    'D': 2,
    'D#': 3, 'EB': 3,
    'E': 4, 'FB': 4,
    'F': 5, 'E#': 5,
    'F#': 6, 'GB': 6,
    'G': 7,
    'G#': 8, 'AB': 8,
    'A': 9,
    'A#': 10, 'BB': 10,
    'B': 11, 'CB': 11
}

SEMITONE_TO_NOTE_NAME = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Standard supported durations in beats (quarter note = 1.0)
VALID_DURATIONS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0]

def midi_to_note_name(midi_number: int) -> str:
    """Converts MIDI note number (0-127) to scientific pitch notation (e.g. 60 -> 'C4')."""
    if not (0 <= midi_number <= 127):
        raise ValueError(f"MIDI note {midi_number} out of valid range (0-127)")
    octave = (midi_number // 12) - 1
    semitone = midi_number % 12
    return f"{SEMITONE_TO_NOTE_NAME[semitone]}{octave}"

def note_name_to_midi(pitch_str: str) -> int:
    """Converts scientific pitch notation (e.g. 'C4', 'F#5', 'Eb3') to MIDI number (0-127)."""
    clean_pitch = pitch_str.strip().upper()
    match = re.match(r"^([A-G][#B]?)(-?\d+)$", clean_pitch)
    if not match:
        raise ValueError(f"Invalid note pitch format: '{pitch_str}'. Expected format like 'C4', 'F#5', or 'Eb3'.")
    note_name, octave_str = match.groups()
    if note_name not in NOTE_NAME_TO_SEMITONE:
        raise ValueError(f"Unknown note name '{note_name}' in pitch '{pitch_str}'.")
    octave = int(octave_str)
    midi_val = (octave + 1) * 12 + NOTE_NAME_TO_SEMITONE[note_name]
    if not (0 <= midi_val <= 127):
        raise ValueError(f"Pitch '{pitch_str}' resolves to MIDI {midi_val}, which is outside 0-127.")
    return midi_val

def snap_to_closest_duration(duration: float) -> float:
    """Snaps an arbitrary duration to the closest supported symbolic duration."""
    if duration <= 0:
        return 0.25
    return min(VALID_DURATIONS, key=lambda d: abs(d - duration))

def parse_note_token(token: str) -> Dict[str, Any]:
    """
    Parses a single note token such as 'C4', 'C4:1.0', 'D#4:0.5', 'REST', 'REST:1.0', 'R:0.5'.
    Returns a dict with 'pitch', 'midi', 'duration'.
    """
    token = token.strip()
    if not token:
        raise ValueError("Empty note token encountered.")

    parts = token.split(':')
    pitch_part = parts[0].strip().upper()
    
    # Parse duration if provided, else default to 1.0 (quarter note)
    duration = 1.0
    if len(parts) > 1:
        try:
            raw_dur = float(parts[1].strip())
            if raw_dur <= 0:
                raise ValueError(f"Duration must be positive, got {raw_dur}")
            duration = snap_to_closest_duration(raw_dur)
        except ValueError as err:
            raise ValueError(f"Invalid duration in token '{token}': {err}")

    # Handle rests
    if pitch_part in ('REST', 'R', '_'):
        return {
            'pitch': 'REST',
            'midi': None,
            'duration': duration,
            'is_rest': True
        }

    # Handle pitched note
    midi_val = note_name_to_midi(pitch_part)
    canonical_pitch = midi_to_note_name(midi_val)
    return {
        'pitch': canonical_pitch,
        'midi': midi_val,
        'duration': duration,
        'is_rest': False
    }

def parse_melody_string(melody_str: str) -> List[Dict[str, Any]]:
    """
    Parses a melody string into a list of note events.
    Supports comma, whitespace, or newline separated tokens.
    Example: 'C4 D4 E4 G4' or 'C4:1.0, D4:0.5, E4:0.5, G4:2.0'
    """
    if not melody_str or not melody_str.strip():
        raise ValueError("Melody input is empty. Please enter notes like 'C4 D4 E4 G4'.")

    # Split by commas or whitespace
    raw_tokens = re.split(r'[\s,]+', melody_str.strip())
    tokens = [t for t in raw_tokens if t]

    if not tokens:
        raise ValueError("No valid note tokens found in input.")

    events = []
    errors = []
    for idx, token in enumerate(tokens):
        try:
            event = parse_note_token(token)
            events.append(event)
        except Exception as e:
            errors.append(f"Token #{idx + 1} ('{token}'): {str(e)}")

    if errors:
        raise ValueError("Invalid notes detected:\n" + "\n".join(errors))

    return events
