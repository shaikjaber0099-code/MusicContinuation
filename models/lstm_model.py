"""
Melody continuation LSTM neural network model in PyTorch.
Predicts next symbolic music token conditioned on previous context.
"""
import os
import json
import torch
import torch.nn as nn
from typing import Dict, Any, Optional, Tuple

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
        """
        x: (batch_size, seq_len) token IDs
        Returns: logits (batch_size, seq_len, vocab_size), hidden state tuple (h, c)
        """
        embeds = self.embedding(x)  # (batch, seq, embed_dim)
        lstm_out, hidden = self.lstm(embeds, hidden)  # (batch, seq, hidden_dim)
        lstm_out = self.dropout(lstm_out)
        logits = self.fc(lstm_out)  # (batch, seq, vocab_size)
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

    @classmethod
    def load_from_checkpoint(cls, dir_path: str, filename: str = "melody_lstm.pt", config_filename: str = "config.json", device: Optional[torch.device] = None) -> "MelodyLSTM":
        model_path = os.path.join(dir_path, filename)
        config_path = os.path.join(dir_path, config_filename)

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Model configuration file missing at '{config_path}'")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model weights file missing at '{model_path}'")

        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)

        device = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model = cls(
            vocab_size=cfg['vocab_size'],
            embedding_dim=cfg.get('embedding_dim', 128),
            hidden_dim=cfg.get('hidden_dim', 256),
            num_layers=cfg.get('num_layers', 2),
            dropout=cfg.get('dropout', 0.2)
        )
        
        state_dict = torch.load(model_path, map_location=device)
        model.load_state_dict(state_dict)
        model.to(device)
        model.eval()
        return model
