"""
Vocabulary definition for symbolic music representation.
Each music event is tokenized as '{PITCH}_{DURATION}', e.g., 'C4_1.0' or 'REST_0.5'.
"""
import json
from typing import Dict, List, Optional, Any
from input.note_parser import midi_to_note_name, VALID_DURATIONS, note_name_to_midi


SPECIAL_TOKENS = ["<PAD>", "<SOS>", "<EOS>", "<UNK>"]
PAD_TOKEN = "<PAD>"
SOS_TOKEN = "<SOS>"
EOS_TOKEN = "<EOS>"
UNK_TOKEN = "<UNK>"

# Common melodic MIDI pitch range: C3 (MIDI 48) to C6 (MIDI 84), plus broader octave 2-6
MIN_PITCH = 36  # C2
MAX_PITCH = 84  # C6

class MusicVocabulary:
    def __init__(self):
        self.token_to_id: Dict[str, int] = {}
        self.id_to_token: Dict[int, str] = {}
        self._build_vocab()

    def _build_vocab(self):
        """Builds token dictionary from special tokens and pitch/duration combinations."""
        tokens = list(SPECIAL_TOKENS)
        
        # Pitches from MIN_PITCH to MAX_PITCH
        pitches = [midi_to_note_name(m) for m in range(MIN_PITCH, MAX_PITCH + 1)]
        pitches.append("REST")

        for pitch in pitches:
            for dur in VALID_DURATIONS:
                token_str = f"{pitch}_{dur}"
                tokens.append(token_str)

        self.token_to_id = {tok: idx for idx, tok in enumerate(tokens)}
        self.id_to_token = {idx: tok for idx, tok in enumerate(tokens)}

    def __len__(self) -> int:
        return len(self.token_to_id)

    @property
    def pad_id(self) -> int:
        return self.token_to_id[PAD_TOKEN]

    @property
    def sos_id(self) -> int:
        return self.token_to_id[SOS_TOKEN]

    @property
    def eos_id(self) -> int:
        return self.token_to_id[EOS_TOKEN]

    @property
    def unk_id(self) -> int:
        return self.token_to_id[UNK_TOKEN]

    def get_id(self, token: str) -> int:
        return self.token_to_id.get(token, self.unk_id)

    def get_token(self, token_id: int) -> str:
        return self.id_to_token.get(token_id, UNK_TOKEN)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'token_to_id': self.token_to_id,
            'id_to_token': {str(k): v for k, v in self.id_to_token.items()},
            'min_pitch': MIN_PITCH,
            'max_pitch': MAX_PITCH,
            'vocab_size': len(self)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MusicVocabulary":
        vocab = cls.__new__(cls)
        vocab.token_to_id = data['token_to_id']
        vocab.id_to_token = {int(k): v for k, v in data['id_to_token'].items()}
        return vocab

    def save(self, filepath: str):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "MusicVocabulary":
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)
