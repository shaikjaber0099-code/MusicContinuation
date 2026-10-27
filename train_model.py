"""
Model Training Script for Music Continuation Tool.
Compiles a rich dataset of classical, folk, and modal melodies, performs key transposition
data augmentation, and trains the MelodyLSTM neural sequence model.
Saves model checkpoint and vocabulary to models/weights/.
"""
import os
import json
import random
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

from preprocessing.vocab import MusicVocabulary
from preprocessing.tokenizer import MusicTokenizer
from models.lstm_model import MelodyLSTM
from input.note_parser import parse_melody_string, midi_to_note_name, snap_to_closest_duration

# Raw Melodic Corpus (Themes, motifs, phrases with durations in beats)
CORPUS = [
    # Beethoven: Ode to Joy (Theme in D/C)
    "E4:1.0 E4:1.0 F4:1.0 G4:1.0 G4:1.0 F4:1.0 E4:1.0 D4:1.0 C4:1.0 C4:1.0 D4:1.0 E4:1.0 E4:1.5 D4:0.5 D4:2.0 "
    "E4:1.0 E4:1.0 F4:1.0 G4:1.0 G4:1.0 F4:1.0 E4:1.0 D4:1.0 C4:1.0 C4:1.0 D4:1.0 E4:1.0 D4:1.5 C4:0.5 C4:2.0 "
    "D4:1.0 D4:1.0 E4:1.0 C4:1.0 D4:1.0 E4:0.5 F4:0.5 E4:1.0 C4:1.0 D4:1.0 E4:0.5 F4:0.5 E4:1.0 D4:1.0 C4:1.0 D4:1.0 G3:2.0",

    # Mozart: Twinkle Twinkle Little Star
    "C4:1.0 C4:1.0 G4:1.0 G4:1.0 A4:1.0 A4:1.0 G4:2.0 F4:1.0 F4:1.0 E4:1.0 E4:1.0 D4:1.0 D4:1.0 C4:2.0 "
    "G4:1.0 G4:1.0 F4:1.0 F4:1.0 E4:1.0 E4:1.0 D4:2.0 G4:1.0 G4:1.0 F4:1.0 F4:1.0 E4:1.0 E4:1.0 D4:2.0 "
    "C4:1.0 C4:1.0 G4:1.0 G4:1.0 A4:1.0 A4:1.0 G4:2.0 F4:1.0 F4:1.0 E4:1.0 E4:1.0 D4:1.0 D4:1.0 C4:2.0",

    # Beethoven: Für Elise Theme
    "E5:0.5 D#5:0.5 E5:0.5 D#5:0.5 E5:0.5 B4:0.5 D5:0.5 C5:0.5 A4:1.0 REST:0.5 C4:0.5 E4:0.5 A4:0.5 B4:1.0 "
    "REST:0.5 E4:0.5 G#4:0.5 B4:0.5 C5:1.0 REST:0.5 E4:0.5 E5:0.5 D#5:0.5 E5:0.5 D#5:0.5 E5:0.5 B4:0.5 D5:0.5 C5:0.5 A4:1.5",

    # Mozart: Eine kleine Nachtmusik Allegro
    "G4:1.5 REST:0.5 D4:1.0 G4:1.5 REST:0.5 D4:1.0 G4:0.5 D4:0.5 G4:0.5 B4:0.5 D5:2.0 "
    "C5:1.5 REST:0.5 A4:1.0 C5:1.5 REST:0.5 A4:1.0 C5:0.5 A4:0.5 F#4:0.5 A4:0.5 D4:2.0",

    # Bach: Minuet in G
    "D5:1.0 G4:0.5 A4:0.5 B4:0.5 C5:0.5 D5:1.0 G4:1.0 G4:1.0 E5:1.0 C5:0.5 D5:0.5 E5:0.5 F#5:0.5 G5:1.0 G4:1.0 G4:1.0 "
    "C5:1.0 D5:0.5 C5:0.5 B4:0.5 A4:0.5 B4:1.0 C5:0.5 B4:0.5 A4:0.5 G4:0.5 F#4:1.0 G4:0.5 A4:0.5 B4:0.5 G4:0.5 A4:2.0",

    # Traditional: Greensleeves
    "E4:1.0 G4:1.5 A4:0.5 B4:1.0 C5:0.5 B4:0.5 A4:1.0 F#4:1.5 D4:0.5 E4:0.5 F#4:0.5 G4:1.0 E4:1.5 E4:0.5 D#4:1.0 E4:0.5 F#4:0.5 B3:2.0 "
    "G4:1.5 A4:0.5 B4:1.0 C5:0.5 B4:0.5 A4:1.0 F#4:1.5 D4:0.5 E4:0.5 F#4:0.5 G4:0.75 F#4:0.25 E4:0.5 D#4:0.5 C#4:0.5 D#4:1.0 E4:2.0",

    # Traditional: Scarborough Fair (Dorian mode)
    "D4:2.0 D4:1.0 A4:1.0 A4:1.0 A4:1.0 E4:1.5 F4:0.5 E4:1.0 D4:3.0 "
    "A4:1.0 C5:1.0 D5:1.0 D5:1.0 C5:1.0 A4:1.0 B4:1.0 G4:1.0 A4:3.0 "
    "D5:2.0 D5:1.0 D5:1.0 C5:1.0 A4:1.0 A4:0.5 G4:0.5 F4:1.0 E4:1.0 D4:3.0",

    # Traditional: Amazing Grace (Pentatonic)
    "D4:1.0 G4:2.0 B4:0.5 G4:0.5 B4:2.0 A4:1.0 G4:2.0 E4:1.0 D4:2.0 "
    "D4:1.0 G4:2.0 B4:0.5 G4:0.5 B4:2.0 A4:1.0 D5:3.0 "
    "B4:1.0 D5:2.0 B4:0.5 G4:0.5 B4:2.0 A4:1.0 G4:2.0 E4:1.0 D4:2.0 D4:1.0 G4:2.0",

    # Blues Lick & Pentatonic Sequence
    "C4:0.5 Eb4:0.5 F4:0.5 F#4:0.5 G4:1.0 Bb4:0.5 C5:1.5 "
    "C5:0.5 Bb4:0.5 G4:0.5 F#4:0.5 F4:0.5 Eb4:0.5 C4:1.5 "
    "REST:0.5 C4:0.5 E4:0.5 G4:0.5 A4:0.5 C5:1.0 D5:0.5 C5:1.5",

    # Lydian / Uplifting Contemporary Motif
    "C4:1.0 E4:1.0 F#4:1.0 G4:1.0 B4:1.0 C5:1.5 D5:0.5 C5:2.0 "
    "G4:1.0 B4:1.0 D5:1.0 F#5:1.0 G5:2.0 E5:1.0 D5:1.0 C5:2.0",

    # Major Arpeggio & Stepwise Motion (I-V-vi-IV)
    "C4:0.5 E4:0.5 G4:0.5 C5:0.5 G4:0.5 B4:0.5 D5:0.5 G5:0.5 "
    "A4:0.5 C5:0.5 E5:0.5 A5:0.5 F4:0.5 A4:0.5 C5:0.5 F5:0.5 "
    "E5:1.0 D5:0.5 C5:0.5 D5:1.0 C5:2.0",

    # Minor Ballad Motif (A Minor)
    "A4:1.0 C5:0.5 B4:0.5 A4:1.0 E4:1.0 F4:1.0 A4:0.5 G4:0.5 F4:1.0 D4:1.0 "
    "E4:1.0 G4:0.5 F4:0.5 E4:1.0 B3:1.0 C4:1.0 D4:0.5 E4:0.5 A4:2.0"
]

def transpose_events(events, semitones: int):
    """Transposes all pitched notes in the sequence by `semitones`."""
    transposed = []
    for ev in events:
        if ev.get('is_rest', False) or ev.get('midi') is None:
            transposed.append(dict(ev))
            continue
        new_midi = ev['midi'] + semitones
        # Keep within valid MIDI pitch range (36-84)
        if 36 <= new_midi <= 84:
            new_ev = dict(ev)
            new_ev['midi'] = new_midi
            new_ev['pitch'] = midi_to_note_name(new_midi)
            transposed.append(new_ev)
        else:
            return None  # Out of range, discard this transposition
    return transposed

class MelodySequenceDataset(Dataset):
    def __init__(self, sequences, seq_len: int = 16):
        self.inputs = []
        self.targets = []
        
        for seq in sequences:
            if len(seq) <= seq_len:
                continue
            for i in range(len(seq) - seq_len):
                self.inputs.append(seq[i : i + seq_len])
                self.targets.append(seq[i + 1 : i + seq_len + 1])

    def __len__(self):
        return len(self.inputs)

    def __getitem__(self, idx):
        return (
            torch.tensor(self.inputs[idx], dtype=torch.long),
            torch.tensor(self.targets[idx], dtype=torch.long)
        )

def train():
    random.seed(42)
    torch.manual_seed(42)

    print("Building vocabulary...")
    vocab = MusicVocabulary()
    tokenizer = MusicTokenizer(vocab)
    print(f"Vocabulary size: {len(vocab)} tokens")

    output_dir = os.path.join(os.path.dirname(__file__), "models", "weights")
    os.makedirs(output_dir, exist_ok=True)
    vocab_file = os.path.join(output_dir, "vocab.json")
    vocab.save(vocab_file)
    print(f"Saved vocabulary to {vocab_file}")

    # Parse raw melodies
    print("Parsing corpus and generating transpositions...")
    all_event_sequences = []
    for raw in CORPUS:
        base_events = parse_melody_string(raw)
        all_event_sequences.append(base_events)
        
        # Transpose across -6 to +6 semitones for key invariance
        for shift in range(-6, 7):
            if shift == 0:
                continue
            transposed = transpose_events(base_events, shift)
            if transposed:
                all_event_sequences.append(transposed)

    print(f"Total melody sequences after data augmentation: {len(all_event_sequences)}")

    # Tokenize sequences
    token_sequences = []
    for seq in all_event_sequences:
        tokens = tokenizer.encode(seq)
        token_sequences.append(tokens)

    # Dataset & DataLoader
    seq_len = 16
    dataset = MelodySequenceDataset(token_sequences, seq_len=seq_len)
    print(f"Created {len(dataset)} training samples (sequence length = {seq_len})")

    dataloader = DataLoader(dataset, batch_size=32, shuffle=True)

    # Initialize Model
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Training on device: {device}")

    model = MelodyLSTM(
        vocab_size=len(vocab),
        embedding_dim=128,
        hidden_dim=256,
        num_layers=2,
        dropout=0.2
    ).to(device)

    criterion = nn.CrossEntropyLoss(ignore_index=vocab.pad_id)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.003, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=35)

    num_epochs = 35
    model.train()
    print("Starting training...")

    for epoch in range(1, num_epochs + 1):
        total_loss = 0.0
        count = 0
        for x_batch, y_batch in dataloader:
            x_batch = x_batch.to(device)
            y_batch = y_batch.to(device)

            optimizer.zero_grad()
            logits, _ = model(x_batch)  # (batch, seq, vocab)
            loss = criterion(logits.view(-1, len(vocab)), y_batch.view(-1))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=2.0)
            optimizer.step()

            total_loss += loss.item()
            count += 1

        scheduler.step()
        avg_loss = total_loss / max(1, count)
        if epoch % 5 == 0 or epoch == 1 or epoch == num_epochs:
            print(f"Epoch {epoch:2d}/{num_epochs:2d} | Avg Cross-Entropy Loss: {avg_loss:.4f}")

    # Save model checkpoint
    model.save_checkpoint(output_dir, filename="melody_lstm.pt", config_filename="config.json")
    print(f"Model checkpoint successfully saved to {output_dir}")

    # Quick test inference
    test_prompt = parse_melody_string("C4 D4 E4 G4")
    print(f"Testing generation on prompt: {[e['pitch'] for e in test_prompt]}...")
    prompt_ids = tokenizer.encode(test_prompt)
    model.eval()
    with torch.no_grad():
        x = torch.tensor([prompt_ids], dtype=torch.long, device=device)
        logits, hidden = model(x)
        next_tok = logits[0, -1, :].argmax().item()
        event = tokenizer.decode([next_tok])
        print(f"Prompt continuation 1st token prediction: {event}")

if __name__ == "__main__":
    train()
