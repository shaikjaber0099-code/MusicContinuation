"""
Sampling strategies for symbolic melody generation.
Supports temperature scaling, top-k, and nucleus (top-p) sampling.
"""
from typing import List, Optional
import torch
import torch.nn.functional as F

def sample_next_token(
    logits: torch.Tensor,
    temperature: float = 0.85,
    top_k: int = 20,
    top_p: float = 0.9,
    banned_token_ids: Optional[List[int]] = None,
    recent_token_ids: Optional[List[int]] = None,
    repetition_penalty: float = 1.15
) -> int:
    """
    Samples next token ID from 1D logits tensor.
    
    Args:
        logits: 1D torch.Tensor of shape (vocab_size,)
        temperature: Softmax temperature (>0.0). Higher = more diverse/creative.
        top_k: Keep only top k highest probability tokens.
        top_p: Nucleus sampling cumulative probability threshold.
        banned_token_ids: Token IDs to suppress (e.g. <PAD>, <SOS>, <UNK>).
        recent_token_ids: Recently generated tokens to apply repetition penalty to.
        repetition_penalty: Penalty factor (>1.0 reduces probability of immediate repeats).
    """
    # Clone to avoid in-place modification
    logits = logits.clone().detach()

    # Suppress banned tokens
    if banned_token_ids:
        for tid in banned_token_ids:
            if 0 <= tid < logits.size(0):
                logits[tid] = -float('inf')

    # Apply repetition penalty
    if recent_token_ids and repetition_penalty != 1.0:
        for tid in set(recent_token_ids):
            if 0 <= tid < logits.size(0):
                if logits[tid] > 0:
                    logits[tid] /= repetition_penalty
                else:
                    logits[tid] *= repetition_penalty

    # Temperature scaling
    temperature = max(1e-4, float(temperature))
    scaled_logits = logits / temperature

    # Top-k filtering
    if top_k > 0 and top_k < scaled_logits.size(0):
        val, _ = torch.topk(scaled_logits, top_k)
        min_topk = val[-1]
        scaled_logits[scaled_logits < min_topk] = -float('inf')

    # Softmax to get probabilities
    probs = F.softmax(scaled_logits, dim=-1)

    # Top-p (nucleus) filtering
    if 0.0 < top_p < 1.0:
        sorted_probs, sorted_indices = torch.sort(probs, descending=True)
        cumulative_probs = torch.cumsum(sorted_probs, dim=-1)

        # Remove tokens with cumulative probability above threshold
        sorted_indices_to_remove = cumulative_probs > top_p
        # Shift indices to keep at least the first token
        sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
        sorted_indices_to_remove[..., 0] = False

        indices_to_remove = sorted_indices[sorted_indices_to_remove]
        probs[indices_to_remove] = 0.0
        # Renormalize
        sum_probs = probs.sum()
        if sum_probs > 0:
            probs = probs / sum_probs
        else:
            # Fallback to uniform over unmasked
            probs = F.softmax(logits, dim=-1)

    # Multinomial sampling
    sampled_id = torch.multinomial(probs, num_samples=1).item()
    return int(sampled_id)
