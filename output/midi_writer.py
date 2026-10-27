"""
MIDI Writer module using mido.
Exports symbolic melody events into valid Standard MIDI Files (.mid).
"""
import io
from typing import List, Dict, Any, Optional
import mido

TICKS_PER_BEAT = 480

def events_to_midi_bytes(
    events: List[Dict[str, Any]],
    bpm: int = 120,
    track_name: str = "Melody Continuation"
) -> bytes:
    """
    Converts a sequence of symbolic melody events into bytes of a valid Standard MIDI File (.mid).
    Guarantees structural validity and playable event timing (FR-10, TC-10).
    """
    if not events:
        raise ValueError("Cannot create MIDI file from empty event list.")

    mid = mido.MidiFile(type=0, ticks_per_beat=TICKS_PER_BEAT)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # Track Name meta-message
    track.append(mido.MetaMessage('track_name', name=track_name, time=0))

    # Tempo meta-message (bpm to microseconds per beat)
    microseconds_per_beat = mido.bpm2tempo(max(40, min(300, bpm)))
    track.append(mido.MetaMessage('set_tempo', tempo=microseconds_per_beat, time=0))

    # Time signature meta-message: 4/4
    track.append(mido.MetaMessage('time_signature', numerator=4, denominator=4, clocks_per_click=24, notated_32nd_notes_per_beat=8, time=0))

    # Program change: Acoustic Grand Piano (program 0)
    track.append(mido.Message('program_change', program=0, time=0))

    pending_rest_ticks = 0

    for ev in events:
        dur_beats = float(ev.get('duration', 1.0))
        dur_ticks = int(round(dur_beats * TICKS_PER_BEAT))
        if dur_ticks <= 0:
            dur_ticks = int(TICKS_PER_BEAT / 4)

        if ev.get('is_rest', False) or ev.get('pitch') == 'REST':
            pending_rest_ticks += dur_ticks
            continue

        midi_pitch = ev.get('midi')
        if midi_pitch is None:
            # Skip invalid event without crashing
            continue

        midi_pitch = max(0, min(127, int(midi_pitch)))
        vel = 95 if ev.get('source') == 'continuation' else 85

        # Note On: delta time is any pending rest ticks
        track.append(mido.Message('note_on', note=midi_pitch, velocity=vel, time=pending_rest_ticks))
        pending_rest_ticks = 0

        # Note Off: delta time is note duration
        track.append(mido.Message('note_off', note=midi_pitch, velocity=0, time=dur_ticks))

    # End of track
    track.append(mido.MetaMessage('end_of_track', time=0))

    # Write to in-memory bytes buffer
    buf = io.BytesIO()
    mid.save(file=buf)
    return buf.getvalue()

def save_events_to_midi_file(
    events: List[Dict[str, Any]],
    filepath: str,
    bpm: int = 120,
    track_name: str = "Melody Continuation"
):
    """Saves melody events directly to a .mid file on disk."""
    data = events_to_midi_bytes(events, bpm=bpm, track_name=track_name)
    with open(filepath, 'wb') as f:
        f.write(data)
