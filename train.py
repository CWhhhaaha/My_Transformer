import torch
from torch.optim import Adam

from config import Config
from data import get_dataloader
from model import build_model
from utils import (
    set_seed,
    get_loss_fn,
    train_one_epoch,
    evaluate,
    save_checkpoint,
    plot_loss,
)


def main():
    cfg = Config()
    set_seed(cfg.seed)
    cfg.verify_data_files()

    device = cfg.device
    print(f"Using device: {device}")

    print("Loading dataloaders...")
    train_loader, src_vocab, tgt_vocab = get_dataloader(cfg, split="train")
    valid_loader, _, _ = get_dataloader(
        cfg,
        split="valid",
        src_vocab=src_vocab,
        tgt_vocab=tgt_vocab,
    )

    pad_idx = src_vocab.stoi[cfg.pad_token]

    model = build_model(
        cfg=cfg,
        src_vocab_size=len(src_vocab),
        tgt_vocab_size=len(tgt_vocab),
        pad_idx=pad_idx,
    ).to(device)

    optimizer = Adam(
        model.parameters(),
        lr=cfg.lr,
        weight_decay=cfg.weight_decay,
    )

    loss_fn = get_loss_fn(pad_idx=tgt_vocab.stoi[cfg.pad_token])

    best_val_loss = float("inf")
    train_losses = []
    val_losses = []

    print("\nStart training...")
    for epoch in range(1, cfg.num_epochs + 1):
        train_loss = train_one_epoch(
            model=model,
            dataloader=train_loader,
            optimizer=optimizer,
            loss_fn=loss_fn,
            device=device,
            cfg=cfg,
        )

        val_loss = evaluate(
            model=model,
            dataloader=valid_loader,
            loss_fn=loss_fn,
            device=device,
        )

        train_losses.append(train_loss)
        val_losses.append(val_loss)

        print(
            f"Epoch [{epoch}/{cfg.num_epochs}] | "
            f"Train Loss: {train_loss:.4f} | "
            f"Valid Loss: {val_loss:.4f}"
        )

        save_checkpoint(model, optimizer, cfg.last_checkpoint_path)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            save_checkpoint(model, optimizer, cfg.best_checkpoint_path)
            print(f"Saved best checkpoint to: {cfg.best_checkpoint_path}")

    plot_loss(train_losses, val_losses, cfg.loss_curve_path)
    print(f"\nTraining finished.")
    print(f"Best val loss: {best_val_loss:.4f}")
    print(f"Loss curve saved to: {cfg.loss_curve_path}")
    print(f"Last checkpoint saved to: {cfg.last_checkpoint_path}")


if __name__ == "__main__":
    main()