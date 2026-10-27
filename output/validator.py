"""
Output validation module.
Verifies that generated events adhere to structural integrity and symbolic music constraints (TC-07).
"""
from typing import List, Dict, Any

def validate_generated_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Checks that every generated event has valid pitch/duration structure.
    Returns status dict with error details if structural check fails.
    """
    if not isinstance(events, list):
        return {'valid': False, 'error': "Generated output must be a list of event objects."}

    if len(events) == 0:
        return {'valid': False, 'error': "Generated output contains zero events."}

    for idx, ev in enumerate(events):
        if not isinstance(ev, dict):
            return {'valid': False, 'error': f"Event at index {idx} is not a dictionary."}

        dur = ev.get('duration')
        if dur is None or not isinstance(dur, (int, float)) or dur <= 0:
            return {'valid': False, 'error': f"Event at index {idx} has invalid duration: {dur}"}

        is_rest = ev.get('is_rest', False)
        pitch = ev.get('pitch')
        midi_val = ev.get('midi')

        if is_rest:
            if pitch != 'REST':
                return {'valid': False, 'error': f"Rest event at index {idx} has non-rest pitch: {pitch}"}
        else:
            if not pitch or not isinstance(pitch, str):
                return {'valid': False, 'error': f"Pitched event at index {idx} missing valid pitch string."}
            if midi_val is None or not (0 <= midi_val <= 127):
                return {'valid': False, 'error': f"Pitched event at index {idx} has invalid MIDI value: {midi_val}"}

    return {'valid': True, 'count': len(events)}
