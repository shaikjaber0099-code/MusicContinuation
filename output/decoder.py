"""
Decoder and musical analytics module.
Computes musical characteristics and prepares events for display and audio rendering.
"""
from typing import List, Dict, Any
from output.validator import validate_generated_events

def analyze_melody_sequence(events: List[Dict[str, Any]], bpm: int = 120) -> Dict[str, Any]:
    """Computes duration, pitch bounds, notes distribution, and timing offsets."""
    validity = validate_generated_events(events)
    if not validity['valid']:
        return {'valid': False, 'error': validity['error']}

    total_beats = 0.0
    pitched_events = []
    annotated = []

    current_beat = 0.0
    seconds_per_beat = 60.0 / bpm

    for ev in events:
        dur = float(ev.get('duration', 1.0))
        item = dict(ev)
        item['start_beat'] = round(current_beat, 3)
        item['start_time_sec'] = round(current_beat * seconds_per_beat, 3)
        item['duration_sec'] = round(dur * seconds_per_beat, 3)

        if not ev.get('is_rest', False) and ev.get('midi') is not None:
            pitched_events.append(ev['midi'])

        annotated.append(item)
        current_beat += dur

    min_midi = min(pitched_events) if pitched_events else None
    max_midi = max(pitched_events) if pitched_events else None

    return {
        'valid': True,
        'events': annotated,
        'count': len(events),
        'pitched_count': len(pitched_events),
        'total_beats': round(current_beat, 2),
        'total_duration_sec': round(current_beat * seconds_per_beat, 2),
        'min_midi': min_midi,
        'max_midi': max_midi,
        'pitch_range_semitones': (max_midi - min_midi) if (min_midi and max_midi) else 0
    }
