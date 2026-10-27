"""
Sampling strategies for symbolic melody generation.
Supports temperature scaling, top-k, and nucleus (top-p) sampling.
Compatible with both PyTorch tensors and NumPy arrays.
"""
from typing import List, Optional, Any
import numpy as np

try:
    import torch
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    F = None
    TORCH_AVAILABLE = False

def sample_next_token(
    logits: Any,
    temperature: float = 0.85,
    top_k: int = 20,
    top_p: float = 0.9,
    banned_token_ids: Optional[List[int]] = None,
    recent_token_ids: Optional[List[int]] = None,
    repetition_penalty: float = 1.15
) -> int:
    """
    Samples next token ID from 1D logits (torch.Tensor or numpy.ndarray).
    """
    if TORCH_AVAILABLE and isinstance(logits, torch.Tensor):
        logits = logits.clone().detach()

        if banned_token_ids:
            for tid in banned_token_ids:
                if 0 <= tid < logits.size(0):
                    logits[tid] = -float('inf')

        if recent_token_ids and repetition_penalty != 1.0:
            for tid in set(recent_token_ids):
                if 0 <= tid < logits.size(0):
                    if logits[tid] > 0:
                        logits[tid] /= repetition_penalty
                    else:
                        logits[tid] *= repetition_penalty

        temperature = max(1e-4, float(temperature))
        scaled_logits = logits / temperature

        if top_k > 0 and top_k < scaled_logits.size(0):
            val, _ = torch.topk(scaled_logits, top_k)
            min_topk = val[-1]
            scaled_logits[scaled_logits < min_topk] = -float('inf')

        probs = F.softmax(scaled_logits, dim=-1)

        if 0.0 < top_p < 1.0:
            sorted_probs, sorted_indices = torch.sort(probs, descending=True)
            cumulative_probs = torch.cumsum(sorted_probs, dim=-1)

            sorted_indices_to_remove = cumulative_probs > top_p
            sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
            sorted_indices_to_remove[..., 0] = False

            indices_to_remove = sorted_indices[sorted_indices_to_remove]
            probs[indices_to_remove] = 0.0
            sum_probs = probs.sum()
            if sum_probs > 0:
                probs = probs / sum_probs
            else:
                probs = F.softmax(logits, dim=-1)

        sampled_id = torch.multinomial(probs, num_samples=1).item()
        return int(sampled_id)

    # NumPy Fallback for serverless / lightweight environments
    if hasattr(logits, 'detach'):
        logits_arr = logits.detach().cpu().numpy()
    elif hasattr(logits, 'numpy'):
        logits_arr = logits.numpy()
    else:
        logits_arr = np.asarray(logits, dtype=np.float32)

    logits_arr = np.copy(logits_arr)

    if banned_token_ids:
        for tid in banned_token_ids:
            if 0 <= tid < len(logits_arr):
                logits_arr[tid] = -1e9

    if recent_token_ids and repetition_penalty != 1.0:
        for tid in set(recent_token_ids):
            if 0 <= tid < len(logits_arr):
                if logits_arr[tid] > 0:
                    logits_arr[tid] /= repetition_penalty
                else:
                    logits_arr[tid] *= repetition_penalty

    temperature = max(1e-4, float(temperature))
    scaled = logits_arr / temperature

    if 0 < top_k < len(scaled):
        thresh = np.partition(scaled, -top_k)[-top_k]
        scaled[scaled < thresh] = -1e9

    shift = scaled - np.max(scaled)
    exp_vals = np.exp(shift)
    probs = exp_vals / np.sum(exp_vals)

    if 0.0 < top_p < 1.0:
        sorted_idx = np.argsort(-probs)
        sorted_p = probs[sorted_idx]
        cum_p = np.cumsum(sorted_p)
        to_remove = cum_p > top_p
        to_remove[1:] = to_remove[:-1].copy()
        to_remove[0] = False
        probs[sorted_idx[to_remove]] = 0.0
        s = np.sum(probs)
        if s > 0:
            probs /= s
        else:
            probs = exp_vals / np.sum(exp_vals)

    return int(np.random.choice(len(probs), p=probs))
