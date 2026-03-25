"""
Comprehensive test script to verify the complete pipeline.
Tests data loading, model architecture, training, evaluation, and inference.
"""

import torch
import os
from pathlib import Path

from config import Config
from data import get_dataloader, read_parallel
from model import build_model, Transformer
from utils import set_seed, get_loss_fn
from inference import translate


def test_config():
    """Test configuration."""
    print("=" * 70)
    print("TEST 1: Configuration")
    print("=" * 70)
    
    cfg = Config()
    print(f"✓ Project root: {cfg.project_root}")
    print(f"✓ Data directory: {cfg.data_dir}")
    print(f"✓ Checkpoint directory: {cfg.checkpoint_dir}")
    print(f"✓ Output directory: {cfg.output_dir}")
    print(f"✓ Device: {cfg.device}")
    print(f"✓ Model config: d_model={cfg.d_model}, n_heads={cfg.n_heads}, "
          f"layers={cfg.num_encoder_layers}")
    print()


def test_data():
    """Test dataset and vocabulary."""
    print("=" * 70)
    print("TEST 2: Dataset & Vocabulary")
    print("=" * 70)
    
    cfg = Config()
    set_seed(cfg.seed)
    
    # Check if data files exist
    required_files = [
        cfg.train_src, cfg.train_tgt,
        cfg.valid_src, cfg.valid_tgt,
        cfg.test_src, cfg.test_tgt,
    ]
    
    for fpath in required_files:
        if not fpath.exists():
            print(f"✗ Missing: {fpath}")
            return False
        else:
            print(f"✓ Found: {fpath}")
    
    # Load and inspect data
    train_pairs = read_parallel(cfg.train_src, cfg.train_tgt)
    print(f"✓ Training pairs: {len(train_pairs)}")
    print(f"  Example: {train_pairs[0]}")
    
    # Load dataloader
    train_loader, src_vocab, tgt_vocab = get_dataloader(cfg, split="train")
    print(f"✓ Source vocab size: {len(src_vocab)}")
    print(f"✓ Target vocab size: {len(tgt_vocab)}")
    print(f"✓ Train batches: {len(train_loader)}")
    
    # Check batch
    for src, tgt in train_loader:
        print(f"✓ Batch shapes - src: {src.shape}, tgt: {tgt.shape}")
        break
    
    print()
    return True


def test_model():
    """Test model architecture."""
    print("=" * 70)
    print("TEST 3: Model Architecture")
    print("=" * 70)
    
    cfg = Config()
    set_seed(cfg.seed)
    
    src_vocab_size = 100
    tgt_vocab_size = 120
    pad_idx = 0
    device = cfg.device
    
    model = Transformer(
        src_vocab_size=src_vocab_size,
        tgt_vocab_size=tgt_vocab_size,
        d_model=cfg.d_model,
        n_heads=cfg.n_heads,
        num_encoder_layers=cfg.num_encoder_layers,
        num_decoder_layers=cfg.num_decoder_layers,
        d_ff=cfg.d_ff,
        max_len=cfg.max_len,
        dropout=cfg.dropout,
        pad_idx=pad_idx,
    ).to(device)
    
    print(f"✓ Model created on device: {device}")
    print(f"✓ Total parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Test forward pass
    batch_size, src_len, tgt_len = 2, 7, 6
    src = torch.randint(1, src_vocab_size, (batch_size, src_len)).to(device)
    tgt = torch.randint(1, tgt_vocab_size, (batch_size, tgt_len)).to(device)
    
    with torch.no_grad():
        output = model(src, tgt)
    
    print(f"✓ Forward pass successful")
    print(f"✓ Output logits shape: {output['logits'].shape}")
    print(f"✓ Expected shape: ({batch_size}, {tgt_len}, {tgt_vocab_size})")
    
    # Test masking
    src_mask = model.make_src_mask(src)
    tgt_mask = model.make_tgt_mask(tgt)
    print(f"✓ Source mask shape: {src_mask.shape}")
    print(f"✓ Target mask shape: {tgt_mask.shape}")
    
    print()


def test_checkpoint():
    """Test checkpoint loading."""
    print("=" * 70)
    print("TEST 4: Checkpoint Loading")
    print("=" * 70)
    
    cfg = Config()
    set_seed(cfg.seed)
    device = cfg.device
    
    # Load data
    train_loader, src_vocab, tgt_vocab = get_dataloader(cfg, split="train")
    
    # Build model
    model = build_model(
        cfg=cfg,
        src_vocab_size=len(src_vocab),
        tgt_vocab_size=len(tgt_vocab),
        pad_idx=src_vocab.stoi[cfg.pad_token],
    ).to(device)
    
    # Check checkpoint
    if cfg.best_checkpoint_path.exists():
        print(f"✓ Checkpoint found: {cfg.best_checkpoint_path}")
        from utils import load_checkpoint
        load_checkpoint(model, None, cfg.best_checkpoint_path, device)
        print(f"✓ Checkpoint loaded successfully")
    else:
        print(f"✗ No checkpoint found at {cfg.best_checkpoint_path}")
        print(f"  Run 'python train.py' first")
    
    print()


def test_inference():
    """Test inference."""
    print("=" * 70)
    print("TEST 5: Inference")
    print("=" * 70)
    
    cfg = Config()
    set_seed(cfg.seed)
    device = cfg.device
    
    # Load data and model
    train_loader, src_vocab, tgt_vocab = get_dataloader(cfg, split="train")
    model = build_model(
        cfg=cfg,
        src_vocab_size=len(src_vocab),
        tgt_vocab_size=len(tgt_vocab),
        pad_idx=src_vocab.stoi[cfg.pad_token],
    ).to(device)
    
    if cfg.best_checkpoint_path.exists():
        from utils import load_checkpoint
        load_checkpoint(model, None, cfg.best_checkpoint_path, device)
        
        # Test translations
        test_sentences = [
            "guten morgen .",
            "wie geht es ?",
            "danke schön .",
        ]
        
        print("Sample translations:")
        for src_text in test_sentences:
            try:
                greedy = translate(src_text, model, src_vocab, tgt_vocab, cfg, device, use_beam=False)
                beam = translate(src_text, model, src_vocab, tgt_vocab, cfg, device, use_beam=True, beam_size=4)
                print(f"  Input:  {src_text}")
                print(f"  Greedy: {greedy}")
                print(f"  Beam:   {beam}")
                print()
            except Exception as e:
                print(f"  ✗ Error with '{src_text}': {e}")
    else:
        print(f"✗ No checkpoint found. Run 'python train.py' first")
    
    print()


def test_evaluation():
    """Test evaluation metrics."""
    print("=" * 70)
    print("TEST 6: Evaluation Metrics")
    print("=" * 70)
    
    from utils import sentence_bleu, corpus_bleu
    
    # Test BLEU calculation
    ref = ["the", "cat", "is", "on", "the", "mat"]
    hyp = ["the", "cat", "is", "on", "a", "mat"]
    
    bleu = sentence_bleu(ref, hyp)
    print(f"✓ BLEU calculation works")
    print(f"  Reference: {' '.join(ref)}")
    print(f"  Hypothesis: {' '.join(hyp)}")
    print(f"  BLEU score: {bleu:.4f}")
    
    # Test corpus BLEU
    refs = [
        ["the", "cat"],
        ["hello", "world"],
    ]
    hyps = [
        ["the", "cat"],
        ["hello", "world"],
    ]
    
    corpus_score = corpus_bleu(refs, hyps)
    print(f"✓ Corpus BLEU: {corpus_score:.4f}")
    
    print()


def test_outputs():
    """Check output files."""
    print("=" * 70)
    print("TEST 7: Output Files")
    print("=" * 70)
    
    cfg = Config()
    outputs = [
        cfg.loss_curve_path,
        cfg.best_checkpoint_path,
        cfg.last_checkpoint_path,
    ]
    
    for fpath in outputs:
        if fpath.exists():
            size = fpath.stat().st_size / (1024 * 1024)  # MB
            print(f"✓ {fpath.name}: {size:.2f} MB")
        else:
            print(f"⊘ {fpath.name}: Not found (run 'python train.py' first)")
    
    print()


def main():
    print("\n" + "=" * 70)
    print("TRANSFORMER MACHINE TRANSLATION - COMPREHENSIVE TEST SUITE")
    print("=" * 70 + "\n")
    
    try:
        test_config()
        test_data()
        test_model()
        test_checkpoint()
        test_inference()
        test_evaluation()
        test_outputs()
        
        print("=" * 70)
        print("✓ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print("\nNext steps:")
        print("  1. python train.py        - Train the model")
        print("  2. python evaluate.py     - Evaluate & visualize")
        print("  3. python inference.py    - Interactive translation")
        print()
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
