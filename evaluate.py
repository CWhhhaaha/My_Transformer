import os
import torch

from config import Config
from data import get_dataloader
from model import build_model
from utils import (
    set_seed,
    get_loss_fn,
    evaluate,
    load_checkpoint,
    greedy_decode,
    beam_search_decode,
    sentence_bleu,
    corpus_bleu,
    average_attention_heads,
    compute_attention_rollout,
    plot_attention_heatmap,
    plot_multihead_attention_grid,
    plot_figure_grid,
)


def ids_to_tokens(token_ids, vocab, pad_idx, bos_idx, eos_idx):
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


def main():
    cfg = Config()
    set_seed(cfg.seed)
    cfg.verify_data_files()

    device = cfg.device
    print(f"Using device: {device}")

    os.makedirs(cfg.output_dir, exist_ok=True)

    print("Loading dataloaders...")
    train_loader, src_vocab, tgt_vocab = get_dataloader(cfg, split="train")
    test_loader, _, _ = get_dataloader(
        cfg,
        split="test",
        src_vocab=src_vocab,
        tgt_vocab=tgt_vocab,
    )

    src_pad_idx = src_vocab.stoi[cfg.pad_token]
    tgt_pad_idx = tgt_vocab.stoi[cfg.pad_token]
    src_bos_idx = src_vocab.stoi[cfg.bos_token]
    src_eos_idx = src_vocab.stoi[cfg.eos_token]
    bos_idx = tgt_vocab.stoi[cfg.bos_token]
    eos_idx = tgt_vocab.stoi[cfg.eos_token]

    model = build_model(
        cfg=cfg,
        src_vocab_size=len(src_vocab),
        tgt_vocab_size=len(tgt_vocab),
        pad_idx=src_pad_idx,
    ).to(device)

    load_checkpoint(model, optimizer=None, path=cfg.best_checkpoint_path, device=device)
    print(f"Loaded checkpoint from: {cfg.best_checkpoint_path}")

    loss_fn = get_loss_fn(pad_idx=tgt_pad_idx)
    test_loss = evaluate(
        model=model,
        dataloader=test_loader,
        loss_fn=loss_fn,
        device=device,
    )
    print(f"Test Loss: {test_loss:.4f}")

    print("\nRunning decoding + BLEU + visualization ...")

    model.eval()

    all_refs = []
    all_greedy_preds = []
    all_beam_preds = []

    shown = 0
    max_show = 3

    with torch.no_grad():
        for src, tgt in test_loader:
            src = src.to(device)
            tgt = tgt.to(device)

            tgt_input = tgt[:, :-1]
            outputs = model(src, tgt_input)

            greedy_pred_ids = greedy_decode(
                model=model,
                src=src,
                max_len=cfg.max_decode_len,
                bos_idx=bos_idx,
                eos_idx=eos_idx,
                device=device,
            )

            batch_size = src.size(0)

            for i in range(batch_size):
                src_i = src[i:i+1]
                tgt_i = tgt[i]

                ref_tokens = ids_to_tokens(
                    tgt_i.detach().cpu().tolist(),
                    tgt_vocab,
                    tgt_pad_idx,
                    bos_idx,
                    eos_idx,
                )

                greedy_tokens = ids_to_tokens(
                    greedy_pred_ids[i].detach().cpu().tolist(),
                    tgt_vocab,
                    tgt_pad_idx,
                    bos_idx,
                    eos_idx,
                )

                beam_pred_ids = beam_search_decode(
                    model=model,
                    src=src_i,
                    max_len=cfg.max_decode_len,
                    bos_idx=bos_idx,
                    eos_idx=eos_idx,
                    device=device,
                    beam_size=max(2, cfg.beam_size),
                )

                beam_tokens = ids_to_tokens(
                    beam_pred_ids[0].detach().cpu().tolist(),
                    tgt_vocab,
                    tgt_pad_idx,
                    bos_idx,
                    eos_idx,
                )

                src_tokens = ids_to_tokens(
                    src_i[0].detach().cpu().tolist(),
                    src_vocab,
                    src_pad_idx,
                    src_bos_idx,
                    src_eos_idx,
                )

                all_refs.append(ref_tokens)
                all_greedy_preds.append(greedy_tokens)
                all_beam_preds.append(beam_tokens)

                greedy_bleu = sentence_bleu(ref_tokens, greedy_tokens)
                beam_bleu = sentence_bleu(ref_tokens, beam_tokens)

                print("\n==============================")
                print(f"Example {len(all_refs)}")
                print("SRC        :", " ".join(src_tokens))
                print("REF        :", " ".join(ref_tokens))
                print("GREEDY PRED:", " ".join(greedy_tokens))
                print("BEAM PRED  :", " ".join(beam_tokens))
                print(f"Greedy BLEU: {greedy_bleu:.4f}")
                print(f"Beam BLEU  : {beam_bleu:.4f}")

                if shown < max_show:
                    enc_attn_layers = [layer_attn[i] for layer_attn in outputs["enc_attn_weights"]]
                    dec_self_layers = [layer_attn[i] for layer_attn in outputs["dec_self_attn"]]
                    cross_layers = [layer_attn[i] for layer_attn in outputs["dec_cross_attn"]]

                    enc_last = average_attention_heads(enc_attn_layers[-1])
                    dec_last = average_attention_heads(dec_self_layers[-1])
                    cross_last = average_attention_heads(cross_layers[-1])

                    rollout = compute_attention_rollout(enc_attn_layers)

                    pred_tokens_for_plot = greedy_tokens if len(greedy_tokens) > 0 else ["<empty>"]
                    dec_plot = dec_last[:len(pred_tokens_for_plot), :len(pred_tokens_for_plot)]
                    cross_plot = cross_last[:len(pred_tokens_for_plot), :len(src_tokens)]
                    rollout_plot = rollout[:len(src_tokens), :len(src_tokens)]
                    enc_plot = enc_last[:len(src_tokens), :len(src_tokens)]

                    plot_attention_heatmap(
                        enc_plot,
                        src_tokens,
                        src_tokens,
                        title="Encoder Self-Attention",
                        save_path=os.path.join(cfg.output_dir, f"enc_attn_{shown}.png"),
                    )

                    plot_attention_heatmap(
                        dec_plot,
                        pred_tokens_for_plot,
                        pred_tokens_for_plot,
                        title="Decoder Self-Attention",
                        save_path=os.path.join(cfg.output_dir, f"dec_self_{shown}.png"),
                    )

                    plot_attention_heatmap(
                        cross_plot,
                        src_tokens,
                        pred_tokens_for_plot,
                        title="Cross-Attention Alignment",
                        save_path=os.path.join(cfg.output_dir, f"cross_attn_{shown}.png"),
                    )

                    plot_attention_heatmap(
                        rollout_plot,
                        src_tokens,
                        src_tokens,
                        title="Encoder Attention Rollout",
                        save_path=os.path.join(cfg.output_dir, f"rollout_{shown}.png"),
                    )

                    plot_multihead_attention_grid(
                        cross_layers[-1][:, :len(pred_tokens_for_plot), :len(src_tokens)],
                        title_prefix="Cross-Attention",
                        save_path=os.path.join(cfg.output_dir, f"cross_heads_{shown}.png"),
                    )

                    plot_figure_grid(
                        enc_plot,
                        dec_plot,
                        cross_plot,
                        rollout_plot,
                        src_tokens,
                        pred_tokens_for_plot,
                        pred_tokens_for_plot,
                        save_path=os.path.join(cfg.output_dir, f"figure_grid_{shown}.png"),
                    )

                    shown += 1

    greedy_corpus_bleu = corpus_bleu(all_refs, all_greedy_preds)
    beam_corpus_bleu = corpus_bleu(all_refs, all_beam_preds)

    print("\n========================================")
    print(f"Corpus Greedy BLEU: {greedy_corpus_bleu:.4f}")
    print(f"Corpus Beam BLEU  : {beam_corpus_bleu:.4f}")
    print(f"Figures saved to  : {cfg.output_dir}")


if __name__ == "__main__":
    main()