import math
import torch
import random
import numpy as np
import matplotlib.pyplot as plt


# =========================
# Seed
# =========================
def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    if torch.backends.mps.is_available():
        try:
            torch.mps.manual_seed(seed)
        except Exception:
            pass


# =========================
# Device helper
# =========================
def move_to_device(batch, device):
    return [x.to(device) for x in batch]


# =========================
# Loss function
# =========================
def get_loss_fn(pad_idx):
    return torch.nn.CrossEntropyLoss(ignore_index=pad_idx)


# =========================
# Train one epoch
# =========================
def train_one_epoch(model, dataloader, optimizer, loss_fn, device, cfg):
    model.train()
    total_loss = 0.0

    for src, tgt in dataloader:
        src = src.to(device)
        tgt = tgt.to(device)

        tgt_input = tgt[:, :-1]
        tgt_output = tgt[:, 1:]

        outputs = model(src, tgt_input)
        logits = outputs["logits"]

        loss = loss_fn(
            logits.reshape(-1, logits.size(-1)),
            tgt_output.reshape(-1)
        )

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.clip_grad_norm)
        optimizer.step()

        total_loss += loss.item()

    return total_loss / len(dataloader)


# =========================
# Evaluate
# =========================
@torch.no_grad()
def evaluate(model, dataloader, loss_fn, device):
    model.eval()
    total_loss = 0.0

    for src, tgt in dataloader:
        src = src.to(device)
        tgt = tgt.to(device)

        tgt_input = tgt[:, :-1]
        tgt_output = tgt[:, 1:]

        outputs = model(src, tgt_input)
        logits = outputs["logits"]

        loss = loss_fn(
            logits.reshape(-1, logits.size(-1)),
            tgt_output.reshape(-1)
        )
        total_loss += loss.item()

    return total_loss / len(dataloader)


# =========================
# Greedy decoding
# =========================
@torch.no_grad()
def greedy_decode(model, src, max_len, bos_idx, eos_idx, device):
    model.eval()

    src = src.to(device)
    src_mask = model.make_src_mask(src)
    enc_output, _ = model.encoder(src, src_mask)

    ys = torch.full((src.size(0), 1), bos_idx, dtype=torch.long, device=device)

    for _ in range(max_len):
        tgt_mask = model.make_tgt_mask(ys)
        dec_out, _, _ = model.decoder(ys, enc_output, tgt_mask, src_mask)
        logits = model.fc_out(dec_out[:, -1])
        next_token = logits.argmax(dim=-1, keepdim=True)
        ys = torch.cat([ys, next_token], dim=1)

        if (next_token == eos_idx).all():
            break

    return ys


# =========================
# Beam search (batch size 1)
# =========================
@torch.no_grad()
def beam_search_decode(model, src, max_len, bos_idx, eos_idx, device, beam_size=4):
    model.eval()

    assert src.size(0) == 1, "beam_search_decode currently supports batch_size=1"

    src = src.to(device)
    src_mask = model.make_src_mask(src)
    enc_output, _ = model.encoder(src, src_mask)

    beams = [(torch.tensor([[bos_idx]], device=device), 0.0, False)]

    for _ in range(max_len):
        candidates = []

        for seq, score, finished in beams:
            if finished:
                candidates.append((seq, score, finished))
                continue

            tgt_mask = model.make_tgt_mask(seq)
            dec_out, _, _ = model.decoder(seq, enc_output, tgt_mask, src_mask)
            logits = model.fc_out(dec_out[:, -1])
            log_probs = torch.log_softmax(logits, dim=-1)

            topk_log_probs, topk_ids = torch.topk(log_probs, beam_size, dim=-1)

            for k in range(beam_size):
                next_id = topk_ids[0, k].view(1, 1)
                next_score = score + topk_log_probs[0, k].item()
                next_seq = torch.cat([seq, next_id], dim=1)
                next_finished = (next_id.item() == eos_idx)
                candidates.append((next_seq, next_score, next_finished))

        candidates = sorted(
            candidates,
            key=lambda x: x[1] / (x[0].size(1) ** 0.7),
            reverse=True
        )
        beams = candidates[:beam_size]

        if all(finished for _, _, finished in beams):
            break

    best_seq = beams[0][0]
    return best_seq


# =========================
# Save / Load
# =========================
def save_checkpoint(model, optimizer, path):
    torch.save({
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
    }, path)


def load_checkpoint(model, optimizer, path, device):
    checkpoint = torch.load(path, map_location=device)
    model.load_state_dict(checkpoint["model"])
    if optimizer is not None and "optimizer" in checkpoint:
        optimizer.load_state_dict(checkpoint["optimizer"])


# =========================
# BLEU
# =========================
def _get_ngrams(tokens, n):
    return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


def sentence_bleu(reference_tokens, candidate_tokens, max_n=4, smooth=True):
    if len(candidate_tokens) == 0:
        return 0.0

    precisions = []
    for n in range(1, max_n + 1):
        ref_ngrams = _get_ngrams(reference_tokens, n)
        cand_ngrams = _get_ngrams(candidate_tokens, n)

        if len(cand_ngrams) == 0:
            precisions.append(1e-9 if smooth else 0.0)
            continue

        ref_count = {}
        for ng in ref_ngrams:
            ref_count[ng] = ref_count.get(ng, 0) + 1

        cand_count = {}
        for ng in cand_ngrams:
            cand_count[ng] = cand_count.get(ng, 0) + 1

        overlap = 0
        for ng, c in cand_count.items():
            overlap += min(c, ref_count.get(ng, 0))

        if smooth:
            precisions.append((overlap + 1) / (len(cand_ngrams) + 1))
        else:
            precisions.append(overlap / len(cand_ngrams) if len(cand_ngrams) > 0 else 0.0)

    log_prec_sum = sum((1.0 / max_n) * math.log(p) for p in precisions if p > 0)

    ref_len = len(reference_tokens)
    cand_len = len(candidate_tokens)

    if cand_len > ref_len:
        bp = 1.0
    else:
        bp = math.exp(1 - ref_len / max(cand_len, 1))

    bleu = bp * math.exp(log_prec_sum)
    return bleu


def corpus_bleu(references, candidates, max_n=4, smooth=True):
    scores = []
    for ref, cand in zip(references, candidates):
        scores.append(sentence_bleu(ref, cand, max_n=max_n, smooth=smooth))
    return float(np.mean(scores)) if scores else 0.0


# =========================
# Plot style
# =========================
def set_plot_style():
    plt.style.use("seaborn-v0_8-paper")
    plt.rcParams.update({
        "font.size": 11,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "figure.figsize": (6, 4),
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


# =========================
# Plot loss
# =========================
def plot_loss(train_losses, val_losses, save_path):
    set_plot_style()
    plt.figure(figsize=(6, 4))
    plt.plot(train_losses, label="Train")
    plt.plot(val_losses, label="Valid")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.title("Training Curve")
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight")
    plt.close()


# =========================
# Attention helpers
# =========================
def average_attention_heads(attn):
    if attn.dim() == 3:
        return attn.mean(dim=0)
    return attn


def compute_attention_rollout(attn_list):
    """
    attn_list: list of [H, L, L] or [L, L]
    returns: [L, L]
    """
    processed = []
    for attn in attn_list:
        attn = average_attention_heads(attn).detach().cpu()
        L = attn.size(0)
        eye = torch.eye(L)
        attn = attn + eye
        attn = attn / attn.sum(dim=-1, keepdim=True)
        processed.append(attn)

    rollout = processed[0]
    for i in range(1, len(processed)):
        rollout = processed[i] @ rollout
    return rollout


def plot_attention_heatmap(attn, x_tokens, y_tokens, title, save_path):
    set_plot_style()
    attn = attn.detach().cpu().numpy()

    plt.figure(figsize=(max(6, 0.45 * len(x_tokens)), max(4, 0.45 * len(y_tokens))))
    im = plt.imshow(attn, aspect="auto", cmap="viridis", origin="lower")
    plt.colorbar(im, fraction=0.046, pad=0.04)
    plt.xticks(range(len(x_tokens)), x_tokens, rotation=45, ha="right")
    plt.yticks(range(len(y_tokens)), y_tokens)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight")
    plt.close()


def plot_multihead_attention_grid(attn, title_prefix, save_path):
    """
    attn: [H, Lq, Lk]
    """
    set_plot_style()
    attn = attn.detach().cpu()
    H = attn.size(0)

    ncols = min(4, H)
    nrows = math.ceil(H / ncols)

    fig, axes = plt.subplots(nrows, ncols, figsize=(3.2 * ncols, 3.0 * nrows))
    if not isinstance(axes, np.ndarray):
        axes = np.array([axes])
    axes = axes.flatten()

    for h in range(H):
        ax = axes[h]
        im = ax.imshow(attn[h].numpy(), aspect="auto", cmap="viridis", origin="lower")
        ax.set_title(f"{title_prefix} Head {h}", fontsize=10)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    for k in range(H, len(axes)):
        axes[k].axis("off")

    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight")
    plt.close()


def plot_figure_grid(enc_attn, dec_self_attn, cross_attn, rollout_attn,
                     src_tokens, tgt_tokens, pred_tokens, save_path):
    set_plot_style()

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    axes = axes.flatten()

    panels = [
        (enc_attn, src_tokens, src_tokens, "Encoder Self-Attention"),
        (dec_self_attn, pred_tokens, pred_tokens, "Decoder Self-Attention"),
        (cross_attn, src_tokens, pred_tokens, "Cross-Attention Alignment"),
        (rollout_attn, src_tokens, src_tokens, "Encoder Attention Rollout"),
    ]

    for ax, (attn, x_tokens, y_tokens, title) in zip(axes, panels):
        arr = attn.detach().cpu().numpy()
        im = ax.imshow(arr, aspect="auto", cmap="viridis", origin="lower")
        ax.set_title(title)
        ax.set_xticks(range(len(x_tokens)))
        ax.set_xticklabels(x_tokens, rotation=45, ha="right")
        ax.set_yticks(range(len(y_tokens)))
        ax.set_yticklabels(y_tokens)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight")
    plt.close()