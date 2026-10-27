"""
Tokenizer for musical sequences.
Encodes lists of symbolic event dicts to token IDs and decodes token IDs back to event dicts.
"""
from typing import List, Dict, Any, Optional
from preprocessing.vocab import MusicVocabulary, UNK_TOKEN, SPECIAL_TOKENS
from input.note_parser import snap_to_closest_duration, note_name_to_midi, midi_to_note_name

def event_to_token(event: Dict[str, Any]) -> str:
    """Converts a single event dict to its string token form, e.g. 'C4_1.0' or 'REST_0.5'."""
    dur = snap_to_closest_duration(event.get('duration', 1.0))
    if event.get('is_rest', False) or event.get('pitch') == 'REST':
        return f"REST_{dur}"
    pitch = event.get('pitch', 'C4').strip().upper()
    return f"{pitch}_{dur}"

def token_to_event(token: str) -> Optional[Dict[str, Any]]:
    """Converts a token string (e.g. 'C4_1.0' or 'REST_0.5') to an event dict."""
    if token in SPECIAL_TOKENS:
        return None
    parts = token.split('_')
    if len(parts) != 2:
        return None
    pitch_str, dur_str = parts[0], parts[1]
    try:
        dur = float(dur_str)
    except ValueError:
        dur = 1.0

    if pitch_str == 'REST':
        return {
            'pitch': 'REST',
            'midi': None,
            'duration': dur,
            'is_rest': True
        }
    
    try:
        midi_val = note_name_to_midi(pitch_str)
        canonical = midi_to_note_name(midi_val)
        return {
            'pitch': canonical,
            'midi': midi_val,
            'duration': dur,
            'is_rest': False
        }
    except Exception:
        return None

class MusicTokenizer:
    def __init__(self, vocab: Optional[MusicVocabulary] = None):
        self.vocab = vocab or MusicVocabulary()

    def encode(self, events: List[Dict[str, Any]], add_sos: bool = False, add_eos: bool = False) -> List[int]:
        """Encodes a sequence of event dicts to a list of token IDs."""
        token_ids = []
        if add_sos:
            token_ids.append(self.vocab.sos_id)

        for ev in events:
            tok = event_to_token(ev)
            tok_id = self.vocab.get_id(tok)
            token_ids.append(tok_id)

        if add_eos:
            token_ids.append(self.vocab.eos_id)

        return token_ids

    def decode(self, token_ids: List[int]) -> List[Dict[str, Any]]:
        """Decodes a list of token IDs back into a list of event dicts."""
        events = []
        for tid in token_ids:
            tok_str = self.vocab.get_token(tid)
            if tok_str in ("<PAD>", "<SOS>", "<EOS>", "<UNK>"):
                continue
            ev = token_to_event(tok_str)
            if ev is not None:
                events.append(ev)
        return events
