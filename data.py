import torch
from torch.utils.data import Dataset, DataLoader
from collections import Counter
from typing import List, Tuple


# =========================
# Vocabulary
# =========================
class Vocab:
    def __init__(self, min_freq=2, max_size=None, specials=None):
        self.min_freq = min_freq
        self.max_size = max_size
        self.specials = specials or ["<pad>", "<unk>", "<bos>", "<eos>"]

        self.itos = []
        self.stoi = {}

    def build(self, sentences: List[List[str]]):
        counter = Counter()
        for sent in sentences:
            counter.update(sent)

        # 加入 special tokens
        self.itos = list(self.specials)

        for token, freq in counter.most_common():
            if freq < self.min_freq:
                continue
            if token in self.itos:
                continue
            self.itos.append(token)
            if self.max_size and len(self.itos) >= self.max_size:
                break

        self.stoi = {tok: idx for idx, tok in enumerate(self.itos)}

    def encode(self, tokens: List[str]):
        return [self.stoi.get(t, self.stoi["<unk>"]) for t in tokens]

    def decode(self, indices: List[int]):
        return [self.itos[i] for i in indices]

    def __len__(self):
        return len(self.itos)


# =========================
# Dataset
# =========================
class TranslationDataset(Dataset):
    def __init__(self, pairs, src_vocab, tgt_vocab):
        self.pairs = pairs
        self.src_vocab = src_vocab
        self.tgt_vocab = tgt_vocab

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, idx):
        src, tgt = self.pairs[idx]

        src_ids = [self.src_vocab.stoi["<bos>"]] + \
                  self.src_vocab.encode(src) + \
                  [self.src_vocab.stoi["<eos>"]]

        tgt_ids = [self.tgt_vocab.stoi["<bos>"]] + \
                  self.tgt_vocab.encode(tgt) + \
                  [self.tgt_vocab.stoi["<eos>"]]

        return torch.tensor(src_ids), torch.tensor(tgt_ids)


# =========================
# Utils
# =========================
def tokenize(line: str):
    return line.strip().split()


def read_parallel(src_path, tgt_path):
    with open(src_path, "r", encoding="utf-8") as f:
        src_lines = [tokenize(line) for line in f]

    with open(tgt_path, "r", encoding="utf-8") as f:
        tgt_lines = [tokenize(line) for line in f]

    assert len(src_lines) == len(tgt_lines), "src/tgt length mismatch"
    return list(zip(src_lines, tgt_lines))


def build_vocab(pairs, cfg):
    src_sentences = [src for src, _ in pairs]
    tgt_sentences = [tgt for _, tgt in pairs]

    src_vocab = Vocab(
        min_freq=cfg.min_freq,
        max_size=cfg.max_vocab_size,
        specials=[cfg.pad_token, cfg.unk_token, cfg.bos_token, cfg.eos_token]
    )
    tgt_vocab = Vocab(
        min_freq=cfg.min_freq,
        max_size=cfg.max_vocab_size,
        specials=[cfg.pad_token, cfg.unk_token, cfg.bos_token, cfg.eos_token]
    )

    src_vocab.build(src_sentences)
    tgt_vocab.build(tgt_sentences)

    print(f"SRC vocab size: {len(src_vocab)}")
    print(f"TGT vocab size: {len(tgt_vocab)}")

    return src_vocab, tgt_vocab


# =========================
# Collate (padding)
# =========================
def collate_fn(batch, pad_idx):
    src_batch, tgt_batch = zip(*batch)

    src_lens = [len(x) for x in src_batch]
    tgt_lens = [len(x) for x in tgt_batch]

    max_src = max(src_lens)
    max_tgt = max(tgt_lens)

    padded_src = torch.full((len(batch), max_src), pad_idx)
    padded_tgt = torch.full((len(batch), max_tgt), pad_idx)

    for i in range(len(batch)):
        padded_src[i, :src_lens[i]] = src_batch[i]
        padded_tgt[i, :tgt_lens[i]] = tgt_batch[i]

    return padded_src, padded_tgt


# =========================
# Main API
# =========================
def get_dataloader(cfg, split="train", src_vocab=None, tgt_vocab=None):
    """
    split: train / valid / test
    """

    if split == "train":
        src_path = cfg.train_src
        tgt_path = cfg.train_tgt
    elif split == "valid":
        src_path = cfg.valid_src
        tgt_path = cfg.valid_tgt
    elif split == "test":
        src_path = cfg.test_src
        tgt_path = cfg.test_tgt
    else:
        raise ValueError(f"Unknown split: {split}")

    print(f"\nLoading {split} data...")
    print("SRC:", src_path)
    print("TGT:", tgt_path)

    pairs = read_parallel(src_path, tgt_path)

    # build vocab only for train
    if split == "train":
        src_vocab, tgt_vocab = build_vocab(pairs, cfg)
    else:
        assert src_vocab is not None and tgt_vocab is not None, \
            "valid/test must use train vocab"

    dataset = TranslationDataset(pairs, src_vocab, tgt_vocab)

    loader = DataLoader(
        dataset,
        batch_size=cfg.batch_size,
        shuffle=(split == "train"),
        num_workers=cfg.num_workers,
        collate_fn=lambda batch: collate_fn(batch, src_vocab.stoi["<pad>"])
    )

    return loader, src_vocab, tgt_vocab