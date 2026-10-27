"""
Playback engine specification and audio event serializer.
Formats symbolic events into time-scheduled audio cues for the Web Audio API synthesis engine.
"""
from typing import List, Dict, Any, Optional

# Standard pitch frequencies in Hz for Web Audio oscillators
SEMITONE_FREQS = {
    'C': 16.35, 'C#': 17.32, 'Db': 17.32,
    'D': 18.35, 'D#': 19.45, 'Eb': 19.45,
    'E': 20.60,
    'F': 21.83, 'F#': 23.12, 'Gb': 23.12,
    'G': 24.50, 'G#': 25.96, 'Ab': 25.96,
    'A': 27.50, 'A#': 29.14, 'Bb': 29.14,
    'B': 30.87
}

def midi_to_freq(midi_number: int) -> float:
    """Converts MIDI note number to frequency in Hertz (A4 = 440 Hz standard)."""
    return round(440.0 * (2.0 ** ((midi_number - 69) / 12.0)), 3)

def prepare_playback_schedule(
    events: List[Dict[str, Any]],
    bpm: int = 120
) -> List[Dict[str, Any]]:
    """
    Transforms melody events into scheduled audio playback notes.
    Each item contains start_time, duration, frequency, pitch, and origin section.
    """
    seconds_per_beat = 60.0 / max(30, min(300, bpm))
    schedule = []
    current_time = 0.0

    for idx, ev in enumerate(events):
        dur_beats = float(ev.get('duration', 1.0))
        dur_sec = round(dur_beats * seconds_per_beat, 4)
        is_rest = ev.get('is_rest', False) or ev.get('pitch') == 'REST'

        if not is_rest and ev.get('midi') is not None:
            freq = midi_to_freq(int(ev['midi']))
            schedule.append({
                'index': idx,
                'pitch': ev.get('pitch', ''),
                'midi': ev['midi'],
                'frequency_hz': freq,
                'start_time': round(current_time, 4),
                'duration': dur_sec,
                'source': ev.get('source', 'original')
            })

        current_time += dur_sec

    return schedule
