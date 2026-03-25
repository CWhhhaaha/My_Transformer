"""
Inference script for machine translation.
Translate English/German sentences using the trained Transformer model.
"""

import torch
from pathlib import Path

from config import Config
from data import get_dataloader, Vocab
from model import build_model
from utils import (
    set_seed,
    load_checkpoint,
    greedy_decode,
    beam_search_decode,
)


def ids_to_tokens(token_ids, vocab, pad_idx, bos_idx, eos_idx):
    """Convert token IDs to tokens."""
    tokens = []
    for idx in token_ids:
        idx = int(idx)
        if idx == pad_idx:
            continue
        if idx == bos_idx:
            continue
        if idx == eos_idx:
            break
        tokens.append(vocab.itos[idx])
    return tokens


def translate(
    src_text: str,
    model,
    src_vocab,
    tgt_vocab,
    cfg,
    device,
    use_beam=True,
    beam_size=4,
):
    """
    Translate a single sentence.
    
    Args:
        src_text: Source sentence (space-separated tokens)
        model: Transformer model
        src_vocab: Source vocabulary
        tgt_vocab: Target vocabulary
        cfg: Configuration object
        device: Device to use
        use_beam: Whether to use beam search
        beam_size: Beam search size
        
    Returns:
        Translated sentence as string
    """
    
    # Tokenize and encode source text
    src_tokens = src_text.strip().split()
    src_ids = [src_vocab.stoi.get(cfg.bos_token, 0)]
    
    for token in src_tokens:
        if token in src_vocab.stoi:
            src_ids.append(src_vocab.stoi[token])
        else:
            src_ids.append(src_vocab.stoi.get(cfg.unk_token, 1))
    
    src_ids.append(src_vocab.stoi.get(cfg.eos_token, 2))
    
    src_tensor = torch.tensor([src_ids], dtype=torch.long, device=device)
    
    # Decode
    model.eval()
    with torch.no_grad():
        if use_beam:
            pred_ids = beam_search_decode(
                model=model,
                src=src_tensor,
                max_len=cfg.max_decode_len,
                bos_idx=tgt_vocab.stoi.get(cfg.bos_token, 0),
                eos_idx=tgt_vocab.stoi.get(cfg.eos_token, 2),
                device=device,
                beam_size=beam_size,
            )
        else:
            pred_ids = greedy_decode(
                model=model,
                src=src_tensor,
                max_len=cfg.max_decode_len,
                bos_idx=tgt_vocab.stoi.get(cfg.bos_token, 0),
                eos_idx=tgt_vocab.stoi.get(cfg.eos_token, 2),
                device=device,
            )
    
    # Convert to tokens
    pred_tokens = ids_to_tokens(
        pred_ids[0].detach().cpu().tolist(),
        tgt_vocab,
        tgt_vocab.stoi.get(cfg.pad_token, 0),
        tgt_vocab.stoi.get(cfg.bos_token, 0),
        tgt_vocab.stoi.get(cfg.eos_token, 2),
    )
    
    return " ".join(pred_tokens)


def main():
    cfg = Config()
    set_seed(cfg.seed)
    
    device = cfg.device
    print(f"Using device: {device}\n")
    
    # Load data and vocab
    print("Loading vocabularies...")
    train_loader, src_vocab, tgt_vocab = get_dataloader(cfg, split="train")
    
    src_pad_idx = src_vocab.stoi[cfg.pad_token]
    
    # Load model
    print("Building model...")
    model = build_model(
        cfg=cfg,
        src_vocab_size=len(src_vocab),
        tgt_vocab_size=len(tgt_vocab),
        pad_idx=src_pad_idx,
    ).to(device)
    
    print(f"Loading checkpoint from: {cfg.best_checkpoint_path}")
    load_checkpoint(model, optimizer=None, path=cfg.best_checkpoint_path, device=device)
    
    print("\n" + "=" * 70)
    print("Transformer Machine Translation - Inference")
    print("=" * 70)
    print(f"Source language: {cfg.src_lang.upper()}")
    print(f"Target language: {cfg.tgt_lang.upper()}")
    print("\nEnter sentences to translate (type 'quit' to exit)")
    print("Example: 'guten morgen .' (German -> English)")
    print("=" * 70 + "\n")
    
    while True:
        try:
            src_text = input("Input: ").strip()
            
            if src_text.lower() == "quit":
                print("Goodbye!")
                break
            
            if not src_text:
                continue
            
            # Greedy decoding
            greedy_output = translate(
                src_text,
                model,
                src_vocab,
                tgt_vocab,
                cfg,
                device,
                use_beam=False,
            )
            
            # Beam search
            beam_output = translate(
                src_text,
                model,
                src_vocab,
                tgt_vocab,
                cfg,
                device,
                use_beam=True,
                beam_size=cfg.beam_size,
            )
            
            print(f"Input:         {src_text}")
            print(f"Greedy:        {greedy_output}")
            print(f"Beam Search:   {beam_output}")
            print()
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            continue


if __name__ == "__main__":
    main()
