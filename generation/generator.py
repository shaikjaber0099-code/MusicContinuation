"""
Generation engine orchestrating conditioned melody continuation.
Preserves original melody and returns verified continuation events.
Supports both PyTorch and high-performance NumPy inference.
"""
import copy
import time
import os
from typing import List, Dict, Any, Optional

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

from models.lstm_model import MelodyLSTM, NumpyMelodyLSTM
from preprocessing.tokenizer import MusicTokenizer
from preprocessing.vocab import MusicVocabulary
from generation.sampler import sample_next_token

class MusicGenerator:
    def __init__(self, model_dir: str, device: Optional[str] = None):
        self.model_dir = model_dir
        if TORCH_AVAILABLE and torch is not None:
            self.device = torch.device(device or ('cuda' if torch.cuda.is_available() else 'cpu'))
        else:
            self.device = 'cpu'

        self.model: Optional[Any] = None
        self.tokenizer: Optional[MusicTokenizer] = None
        self.vocab: Optional[MusicVocabulary] = None
        self.is_loaded = False
        self.load_error: Optional[str] = None

        self._load_pipeline()

    def _load_pipeline(self):
        """Loads vocabulary and model weights. Sets load_error if unavailable."""
        vocab_path = os.path.join(self.model_dir, "vocab.json")
        model_pt_path = os.path.join(self.model_dir, "melody_lstm.pt")
        model_npz_path = os.path.join(self.model_dir, "melody_lstm.npz")
        config_path = os.path.join(self.model_dir, "config.json")

        has_weights = os.path.exists(model_pt_path) or os.path.exists(model_npz_path)

        if not os.path.exists(vocab_path) or not has_weights or not os.path.exists(config_path):
            self.is_loaded = False
            self.load_error = (
                f"Model artifacts not found in '{self.model_dir}'. "
                "Ensure 'melody_lstm.npz' or 'melody_lstm.pt', 'vocab.json', and 'config.json' exist."
            )
            return

        try:
            self.vocab = MusicVocabulary.load(vocab_path)
            self.tokenizer = MusicTokenizer(self.vocab)
            
            # Prefer NumPy if torch is absent, or if npz exists and torch is not loaded
            if not TORCH_AVAILABLE or (os.path.exists(model_npz_path) and not os.path.exists(model_pt_path)):
                self.model = NumpyMelodyLSTM.load_from_checkpoint(self.model_dir)
            else:
                self.model = MelodyLSTM.load_from_checkpoint(self.model_dir, device=self.device)

            self.is_loaded = True
            self.load_error = None
        except Exception as e:
            self.is_loaded = False
            self.load_error = f"Failed to load model pipeline: {str(e)}"

    def check_availability(self) -> Dict[str, Any]:
        """Returns model status and setup details."""
        if not self.is_loaded:
            return {
                'available': False,
                'error': self.load_error or "Model is not initialized."
            }
        return {
            'available': True,
            'device': str(self.device),
            'vocab_size': len(self.vocab),
            'model_type': 'MelodyLSTM'
        }

    def generate(
        self,
        input_events: List[Dict[str, Any]],
        num_events: int = 16,
        temperature: float = 0.85,
        top_k: int = 20,
        top_p: float = 0.9,
        repetition_penalty: float = 1.15
    ) -> Dict[str, Any]:
        """
        Generates continuation events conditioned on the given input_events.
        Guarantees input preservation (FR-07, NFR-10).
        """
        if not self.is_loaded or self.model is None:
            raise RuntimeError(
                "The music model is not available right now. Check the model setup and try again."
            )

        if not input_events:
            raise ValueError("Input events sequence is empty. Provide at least one note.")

        start_time = time.perf_counter()

        # Deep copy original events to guarantee zero mutation
        original_events = copy.deepcopy(input_events)

        # Tokenize input sequence
        prompt_ids = self.tokenizer.encode(original_events, add_sos=False, add_eos=False)
        if not prompt_ids:
            raise ValueError("Input events could not be encoded into known vocabulary tokens.")

        # Prepare banned tokens: PAD, SOS, EOS, UNK
        banned = [
            self.vocab.pad_id,
            self.vocab.sos_id,
            self.vocab.eos_id,
            self.vocab.unk_id
        ]

        # Feed prompt through model to build hidden state
        self.model.eval()

        if TORCH_AVAILABLE and hasattr(self.model, 'parameters'):
            with torch.no_grad():
                x_prompt = torch.tensor([prompt_ids], dtype=torch.long, device=self.device)
                logits, hidden = self.model(x_prompt)
                next_logit = logits[0, -1, :]

                generated_ids = []
                recent_ids = list(prompt_ids[-4:])
                curr_logit = next_logit
                for _ in range(num_events):
                    next_token_id = sample_next_token(
                        logits=curr_logit,
                        temperature=temperature,
                        top_k=top_k,
                        top_p=top_p,
                        banned_token_ids=banned,
                        recent_token_ids=recent_ids,
                        repetition_penalty=repetition_penalty
                    )
                    generated_ids.append(next_token_id)
                    recent_ids.append(next_token_id)
                    if len(recent_ids) > 6:
                        recent_ids.pop(0)

                    x_next = torch.tensor([[next_token_id]], dtype=torch.long, device=self.device)
                    step_logits, hidden = self.model(x_next, hidden)
                    curr_logit = step_logits[0, -1, :]
        else:
            # High-speed NumPy inference engine
            logits, hidden = self.model(prompt_ids)
            next_logit = logits[0, -1]

            generated_ids = []
            recent_ids = list(prompt_ids[-4:])
            curr_logit = next_logit
            for _ in range(num_events):
                next_token_id = sample_next_token(
                    logits=curr_logit,
                    temperature=temperature,
                    top_k=top_k,
                    top_p=top_p,
                    banned_token_ids=banned,
                    recent_token_ids=recent_ids,
                    repetition_penalty=repetition_penalty
                )
                generated_ids.append(next_token_id)
                recent_ids.append(next_token_id)
                if len(recent_ids) > 6:
                    recent_ids.pop(0)

                step_logits, hidden = self.model([next_token_id], hidden)
                curr_logit = step_logits[0, -1]

        # Decode generated token IDs back to event dicts
        continuation_events = self.tokenizer.decode(generated_ids)

        end_time = time.perf_counter()
        gen_duration_sec = end_time - start_time

        # Build combined events with explicit source tags
        annotated_orig = []
        for ev in original_events:
            item = copy.deepcopy(ev)
            item['source'] = 'original'
            annotated_orig.append(item)

        annotated_cont = []
        for ev in continuation_events:
            item = copy.deepcopy(ev)
            item['source'] = 'continuation'
            annotated_cont.append(item)

        combined_events = annotated_orig + annotated_cont

        return {
            'original_events': annotated_orig,
            'continuation_events': annotated_cont,
            'combined_events': combined_events,
            'original_count': len(annotated_orig),
            'continuation_count': len(annotated_cont),
            'total_count': len(combined_events),
            'generation_time_seconds': round(gen_duration_sec, 4),
            'temperature': temperature,
            'num_requested': num_events,
            'model_info': {
                'type': 'MelodyLSTM',
                'device': str(self.device)
            }
        }
