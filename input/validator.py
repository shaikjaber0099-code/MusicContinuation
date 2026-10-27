"""
Input Validator module for the Music Continuation Tool.
Handles validation of manual note entry and MIDI uploads, providing actionable error feedback.
"""
from typing import Dict, Any, Optional, List
from input.note_parser import parse_melody_string
from input.midi_parser import parse_midi_bytes, validate_midi_extension

MIN_MELODY_EVENTS = 1
MAX_MELODY_EVENTS = 128

def validate_melody_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validates structural properties of parsed melody events."""
    if not events:
        return {
            'valid': False,
            'error_code': 'EMPTY_INPUT',
            'error': "Add a few notes or upload a supported MIDI file to get started."
        }
        
    if len(events) < MIN_MELODY_EVENTS:
        return {
            'valid': False,
            'error_code': 'TOO_SHORT',
            'error': f"Melody is too short. Please provide at least {MIN_MELODY_EVENTS} note(s)."
        }

    if len(events) > MAX_MELODY_EVENTS:
        return {
            'valid': False,
            'error_code': 'TOO_LONG',
            'error': f"Melody contains {len(events)} notes, exceeding the maximum limit of {MAX_MELODY_EVENTS}."
        }

    # Ensure at least one pitched note (not only rests)
    pitched_notes = [e for e in events if not e.get('is_rest', False)]
    if not pitched_notes:
        return {
            'valid': False,
            'error_code': 'ONLY_RESTS',
            'error': "The melody contains only rests. Please include at least one pitched note (e.g., C4, D4, E4)."
        }

    # Format preview string
    preview_parts = []
    total_beats = 0.0
    for ev in events:
        dur = ev.get('duration', 1.0)
        total_beats += dur
        if ev.get('is_rest', False):
            preview_parts.append(f"REST({dur}b)")
        else:
            preview_parts.append(f"{ev['pitch']}")

    return {
        'valid': True,
        'events': events,
        'count': len(events),
        'pitched_count': len(pitched_notes),
        'total_beats': round(total_beats, 2),
        'preview_str': "  ".join(preview_parts[:16]) + ("..." if len(preview_parts) > 16 else "")
    }

def validate_text_melody(melody_text: str) -> Dict[str, Any]:
    """Validates user-entered note text."""
    if not melody_text or not melody_text.strip():
        return {
            'valid': False,
            'error_code': 'EMPTY_INPUT',
            'error': "Add a few notes or upload a supported MIDI file to get started."
        }

    try:
        events = parse_melody_string(melody_text)
    except ValueError as err:
        return {
            'valid': False,
            'error_code': 'INVALID_MELODY',
            'error': f"We couldn't read this melody. {str(err)} Example: 'C4 D4 E4 G4 A4'."
        }

    result = validate_melody_events(events)
    if result['valid']:
        result['source'] = 'manual'
    return result

def validate_midi_file(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Validates an uploaded MIDI file."""
    if not file_bytes:
        return {
            'valid': False,
            'error_code': 'EMPTY_INPUT',
            'error': "Add a few notes or upload a supported MIDI file to get started."
        }

    if not validate_midi_extension(filename):
        return {
            'valid': False,
            'error_code': 'UNSUPPORTED_FILE',
            'error': f"This file type is not supported ('{filename}'). Choose a compatible MIDI file (.mid or .midi)."
        }

    try:
        events = parse_midi_bytes(file_bytes, filename)
    except ValueError as err:
        return {
            'valid': False,
            'error_code': 'INVALID_MELODY',
            'error': f"We couldn't read this MIDI melody. {str(err)}"
        }

    result = validate_melody_events(events)
    if result['valid']:
        result['source'] = 'midi'
        result['filename'] = filename
    return result
