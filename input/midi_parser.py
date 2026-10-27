"""
MIDI parser module.
Safely validates and parses uploaded MIDI files into symbolic melody events.
"""
from typing import List, Dict, Any, Tuple, Optional
import io
import mido
from input.note_parser import midi_to_note_name, snap_to_closest_duration

def validate_midi_extension(filename: str) -> bool:
    """Checks whether the filename has a supported MIDI extension (.mid or .midi)."""
    if not filename:
        return False
    lower = filename.lower()
    return lower.endswith('.mid') or lower.endswith('.midi')

def parse_midi_bytes(file_bytes: bytes, filename: str = "upload.mid") -> List[Dict[str, Any]]:
    """
    Parses raw bytes of a MIDI file.
    Validates structure and extracts melody notes into symbolic events.
    Raises ValueError with actionable message if invalid.
    """
    if not validate_midi_extension(filename):
        raise ValueError(
            f"Unsupported file extension for '{filename}'. Please upload a standard .mid or .midi file."
        )

    if not file_bytes or len(file_bytes) < 14:  # Minimum MIDI header length is 14 bytes
        raise ValueError(
            "The uploaded file is empty or too short to be a valid MIDI file. Please select a valid MIDI file."
        )

    # Check MIDI Header magic bytes: 'MThd'
    if not file_bytes.startswith(b'MThd'):
        raise ValueError(
            "Corrupt or non-MIDI file: File header does not contain standard MIDI 'MThd' marker."
        )

    try:
        midi_file = mido.MidiFile(file=io.BytesIO(file_bytes))
    except Exception as err:
        raise ValueError(
            f"Failed to parse MIDI file content ({type(err).__name__}: {str(err)}). "
            "The file may be corrupted or use an unsupported MIDI format."
        )

    ticks_per_beat = midi_file.ticks_per_beat or 480

    # Extract note_on and note_off events with absolute tick times
    events = []
    
    # Process tracks
    for track_idx, track in enumerate(midi_file.tracks):
        abs_ticks = 0
        active_notes = {}  # note_num -> (start_ticks, velocity)
        
        for msg in track:
            abs_ticks += msg.time
            
            if msg.type == 'note_on' and msg.velocity > 0:
                # If note already active on this pitch, close it
                if msg.note in active_notes:
                    start_t, vel = active_notes.pop(msg.note)
                    dur_ticks = max(1, abs_ticks - start_t)
                    events.append({
                        'start_ticks': start_t,
                        'end_ticks': abs_ticks,
                        'midi': msg.note,
                        'duration_ticks': dur_ticks,
                        'track': track_idx
                    })
                active_notes[msg.note] = (abs_ticks, msg.velocity)
                
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in active_notes:
                    start_t, vel = active_notes.pop(msg.note)
                    dur_ticks = max(1, abs_ticks - start_t)
                    events.append({
                        'start_ticks': start_t,
                        'end_ticks': abs_ticks,
                        'midi': msg.note,
                        'duration_ticks': dur_ticks,
                        'track': track_idx
                    })
                    
        # Flush any remaining unclosed notes
        for note_num, (start_t, vel) in active_notes.items():
            dur_ticks = max(1, abs_ticks - start_t)
            if dur_ticks > 0:
                events.append({
                    'start_ticks': start_t,
                    'end_ticks': abs_ticks,
                    'midi': note_num,
                    'duration_ticks': dur_ticks,
                    'track': track_idx
                })

    if not events:
        raise ValueError(
            "No playable note events found in this MIDI file. Please upload a MIDI file containing melody notes."
        )

    # Sort events by start time, then by pitch (highest pitch first if chord)
    events.sort(key=lambda x: (x['start_ticks'], -x['midi']))

    # Monophonic melody extraction: filter to highest pitch note per time window
    melody_events = []
    last_end = 0

    for ev in events:
        start_t = ev['start_ticks']
        # If there is a noticeable rest before this note, insert a rest event
        if start_t > last_end and last_end > 0:
            rest_ticks = start_t - last_end
            rest_beats = rest_ticks / ticks_per_beat
            if rest_beats >= 0.25:
                snapped_rest = snap_to_closest_duration(rest_beats)
                melody_events.append({
                    'pitch': 'REST',
                    'midi': None,
                    'duration': snapped_rest,
                    'is_rest': True
                })

        duration_beats = ev['duration_ticks'] / ticks_per_beat
        snapped_dur = snap_to_closest_duration(duration_beats)
        midi_num = ev['midi']
        
        # Avoid zero/sub-minimum notes
        try:
            pitch_name = midi_to_note_name(midi_num)
        except Exception:
            continue

        melody_events.append({
            'pitch': pitch_name,
            'midi': midi_num,
            'duration': snapped_dur,
            'is_rest': False
        })
        last_end = max(last_end, ev['end_ticks'])

    if not melody_events:
        raise ValueError(
            "Could not extract a clean melodic sequence from the MIDI file. Please check the file's track notes."
        )

    return melody_events
