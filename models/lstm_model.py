"""
Melody continuation LSTM neural network model.
Supports PyTorch (for training & GPU inference) and lightweight NumPy inference
(for serverless deployment on Vercel without massive PyTorch wheel sizes).
"""
import os
import json
from typing import Dict, Any, Optional, Tuple, Union
import numpy as np

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    nn = None
    TORCH_AVAILABLE = False


class NumpyMelodyLSTM:
    """
    Lightweight, high-performance NumPy-based LSTM inference runner.
    Mathematically identical forward pass to PyTorch MelodyLSTM.
    Zero PyTorch dependency for ultra-lightweight serverless deployment (<35MB).
    """
    def __init__(self, weights: Dict[str, np.ndarray], config: Dict[str, Any]):
        self.weights = weights
        self.config = config
        self.vocab_size = config['vocab_size']
        self.embedding_dim = config.get('embedding_dim', 128)
        self.hidden_dim = config.get('hidden_dim', 256)
        self.num_layers = config.get('num_layers', 2)

    def eval(self):
        return self

    def __call__(self, x, hidden=None):
        return self.forward(x, hidden)

    def forward(self, x, hidden=None):
        if hasattr(x, 'tolist'):
            tokens = x.tolist()
            if isinstance(tokens[0], list):
                tokens = tokens[0]
        elif isinstance(x, list):
            tokens = x[0] if isinstance(x[0], list) else x
        else:
            tokens = list(x)

        emb_w = self.weights['embedding.weight']

        if hidden is None:
            h = [np.zeros(self.hidden_dim, dtype=np.float32) for _ in range(self.num_layers)]
            c = [np.zeros(self.hidden_dim, dtype=np.float32) for _ in range(self.num_layers)]
        else:
            h, c = hidden
            if hasattr(h[0], 'cpu'):
                h = [hi.cpu().numpy() for hi in h]
                c = [ci.cpu().numpy() for ci in c]

        logits_list = []
        for t_id in tokens:
            val = emb_w[t_id]
            for l in range(self.num_layers):
                w_ih = self.weights[f'lstm.weight_ih_l{l}']
                w_hh = self.weights[f'lstm.weight_hh_l{l}']
                b_ih = self.weights[f'lstm.bias_ih_l{l}']
                b_hh = self.weights[f'lstm.bias_hh_l{l}']

                gates = np.dot(w_ih, val) + b_ih + np.dot(w_hh, h[l]) + b_hh
                i_gate = 1.0 / (1.0 + np.exp(-gates[0:self.hidden_dim]))
                f_gate = 1.0 / (1.0 + np.exp(-gates[self.hidden_dim:2*self.hidden_dim]))
                g_gate = np.tanh(gates[2*self.hidden_dim:3*self.hidden_dim])
                o_gate = 1.0 / (1.0 + np.exp(-gates[3*self.hidden_dim:4*self.hidden_dim]))

                c[l] = f_gate * c[l] + i_gate * g_gate
                h[l] = o_gate * np.tanh(c[l])
                val = h[l]

            fc_w = self.weights['fc.weight']
            fc_b = self.weights['fc.bias']
            logit = np.dot(fc_w, val) + fc_b
            logits_list.append(logit)

        return np.array([logits_list], dtype=np.float32), (h, c)

    def get_config(self) -> Dict[str, Any]:
        return self.config

    @classmethod
    def load_from_checkpoint(cls, dir_path: str, filename: str = "melody_lstm.npz", config_filename: str = "config.json") -> "NumpyMelodyLSTM":
        config_path = os.path.join(dir_path, config_filename)
        model_path = os.path.join(dir_path, filename)

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Model configuration file missing at '{config_path}'")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"NumPy weights file missing at '{model_path}'")

        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)

        data = np.load(model_path)
        weights = {k: data[k] for k in data.files}
        return cls(weights=weights, config=cfg)


if TORCH_AVAILABLE:
    class MelodyLSTM(nn.Module):
        def __init__(
            self,
            vocab_size: int,
            embedding_dim: int = 128,
            hidden_dim: int = 256,
            num_layers: int = 2,
            dropout: float = 0.2
        ):
            super().__init__()
            self.vocab_size = vocab_size
            self.embedding_dim = embedding_dim
            self.hidden_dim = hidden_dim
            self.num_layers = num_layers
            self.dropout_rate = dropout

            self.embedding = nn.Embedding(vocab_size, embedding_dim)
            self.lstm = nn.LSTM(
                input_size=embedding_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0.0
            )
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Linear(hidden_dim, vocab_size)

        def forward(
            self,
            x: torch.Tensor,
            hidden: Optional[Tuple[torch.Tensor, torch.Tensor]] = None
        ) -> Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
            embeds = self.embedding(x)
            lstm_out, hidden = self.lstm(embeds, hidden)
            lstm_out = self.dropout(lstm_out)
            logits = self.fc(lstm_out)
            return logits, hidden

        def init_hidden(self, batch_size: int, device: torch.device) -> Tuple[torch.Tensor, torch.Tensor]:
            h0 = torch.zeros(self.num_layers, batch_size, self.hidden_dim, device=device)
            c0 = torch.zeros(self.num_layers, batch_size, self.hidden_dim, device=device)
            return (h0, c0)

        def get_config(self) -> Dict[str, Any]:
            return {
                'vocab_size': self.vocab_size,
                'embedding_dim': self.embedding_dim,
                'hidden_dim': self.hidden_dim,
                'num_layers': self.num_layers,
                'dropout': self.dropout_rate,
                'model_type': 'LSTM'
            }

        def save_checkpoint(self, dir_path: str, filename: str = "melody_lstm.pt", config_filename: str = "config.json"):
            os.makedirs(dir_path, exist_ok=True)
            model_path = os.path.join(dir_path, filename)
            config_path = os.path.join(dir_path, config_filename)
            
            torch.save(self.state_dict(), model_path)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.get_config(), f, indent=2)

            # Also save .npz for lightweight serverless environments
            npz_dict = {k: v.cpu().numpy() for k, v in self.state_dict().items()}
            npz_path = os.path.join(dir_path, "melody_lstm.npz")
            np.savez_compressed(npz_path, **npz_dict)

        @classmethod
        def load_from_checkpoint(
            cls,
            dir_path: str,
            filename: str = "melody_lstm.pt",
            config_filename: str = "config.json",
            device: Optional[Any] = None
        ) -> Any:
            model_path = os.path.join(dir_path, filename)
            config_path = os.path.join(dir_path, config_filename)
            npz_path = os.path.join(dir_path, "melody_lstm.npz")

            if not os.path.exists(config_path):
                raise FileNotFoundError(f"Model configuration file missing at '{config_path}'")

            # Fallback to NumPy if .pt is missing or in lightweight mode
            if not os.path.exists(model_path):
                if os.path.exists(npz_path):
                    return NumpyMelodyLSTM.load_from_checkpoint(dir_path)
                raise FileNotFoundError(f"Model weights file missing at '{model_path}'")

            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)

            dev = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            model = cls(
                vocab_size=cfg['vocab_size'],
                embedding_dim=cfg.get('embedding_dim', 128),
                hidden_dim=cfg.get('hidden_dim', 256),
                num_layers=cfg.get('num_layers', 2),
                dropout=cfg.get('dropout', 0.2)
            )
            
            state_dict = torch.load(model_path, map_location=dev)
            model.load_state_dict(state_dict)
            model.to(dev)
            model.eval()
            return model
else:
    # Torch is not installed (Vercel serverless mode)
    MelodyLSTM = NumpyMelodyLSTM
