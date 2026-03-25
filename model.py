import math
import torch
import torch.nn as nn


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(dropout)

        pe = torch.zeros(max_len, d_model)  # [max_len, d_model]
        position = torch.arange(0, max_len, dtype=torch.float32).unsqueeze(1)  # [max_len, 1]
        div_term = torch.exp(
            torch.arange(0, d_model, 2, dtype=torch.float32) * (-math.log(10000.0) / d_model)
        )

        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)

        pe = pe.unsqueeze(0)  # [1, max_len, d_model]
        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: [B, L, D]
        """
        x = x + self.pe[:, : x.size(1)]
        return self.dropout(x)


class MultiHeadAttention(nn.Module):
    def __init__(self, d_model: int, n_heads: int, dropout: float = 0.1):
        super().__init__()
        assert d_model % n_heads == 0, "d_model must be divisible by n_heads"

        self.d_model = d_model
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads

        self.w_q = nn.Linear(d_model, d_model)
        self.w_k = nn.Linear(d_model, d_model)
        self.w_v = nn.Linear(d_model, d_model)
        self.w_o = nn.Linear(d_model, d_model)

        self.dropout = nn.Dropout(dropout)
        self.scale = math.sqrt(self.head_dim)

    def forward(
        self,
        query: torch.Tensor,
        key: torch.Tensor,
        value: torch.Tensor,
        mask: torch.Tensor = None,
    ):
        """
        query: [B, Lq, D]
        key:   [B, Lk, D]
        value: [B, Lv, D]
        mask:  broadcastable to [B, H, Lq, Lk]
               valid positions = True / 1
        """
        B = query.size(0)

        Q = self.w_q(query)  # [B, Lq, D]
        K = self.w_k(key)    # [B, Lk, D]
        V = self.w_v(value)  # [B, Lv, D]

        Q = Q.view(B, -1, self.n_heads, self.head_dim).transpose(1, 2)  # [B, H, Lq, Hd]
        K = K.view(B, -1, self.n_heads, self.head_dim).transpose(1, 2)  # [B, H, Lk, Hd]
        V = V.view(B, -1, self.n_heads, self.head_dim).transpose(1, 2)  # [B, H, Lv, Hd]

        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale  # [B, H, Lq, Lk]

        if mask is not None:
            mask = mask.to(dtype=torch.bool, device=scores.device)
            scores = scores.masked_fill(~mask, float("-inf"))

        attn = torch.softmax(scores, dim=-1)
        attn = self.dropout(attn)

        context = torch.matmul(attn, V)  # [B, H, Lq, Hd]
        context = context.transpose(1, 2).contiguous().view(B, -1, self.d_model)  # [B, Lq, D]

        output = self.w_o(context)  # [B, Lq, D]
        return output, attn


class FeedForward(nn.Module):
    def __init__(self, d_model: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, d_model),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class EncoderLayer(nn.Module):
    def __init__(self, d_model: int, n_heads: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.self_attn = MultiHeadAttention(d_model, n_heads, dropout)
        self.ffn = FeedForward(d_model, d_ff, dropout)

        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, src_mask: torch.Tensor = None):
        attn_out, attn_weights = self.self_attn(x, x, x, src_mask)
        x = self.norm1(x + self.dropout1(attn_out))

        ffn_out = self.ffn(x)
        x = self.norm2(x + self.dropout2(ffn_out))

        return x, attn_weights


class DecoderLayer(nn.Module):
    def __init__(self, d_model: int, n_heads: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.self_attn = MultiHeadAttention(d_model, n_heads, dropout)
        self.cross_attn = MultiHeadAttention(d_model, n_heads, dropout)
        self.ffn = FeedForward(d_model, d_ff, dropout)

        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.norm3 = nn.LayerNorm(d_model)

        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)
        self.dropout3 = nn.Dropout(dropout)

    def forward(
        self,
        x: torch.Tensor,
        enc_output: torch.Tensor,
        tgt_mask: torch.Tensor = None,
        src_mask: torch.Tensor = None,
    ):
        self_attn_out, self_attn_weights = self.self_attn(x, x, x, tgt_mask)
        x = self.norm1(x + self.dropout1(self_attn_out))

        cross_attn_out, cross_attn_weights = self.cross_attn(x, enc_output, enc_output, src_mask)
        x = self.norm2(x + self.dropout2(cross_attn_out))

        ffn_out = self.ffn(x)
        x = self.norm3(x + self.dropout3(ffn_out))

        return x, self_attn_weights, cross_attn_weights


class Encoder(nn.Module):
    def __init__(
        self,
        vocab_size: int,
        d_model: int,
        n_heads: int,
        num_layers: int,
        d_ff: int,
        max_len: int,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.positional_encoding = PositionalEncoding(d_model, max_len, dropout)
        self.dropout = nn.Dropout(dropout)

        self.layers = nn.ModuleList(
            [EncoderLayer(d_model, n_heads, d_ff, dropout) for _ in range(num_layers)]
        )

        self.d_model = d_model

    def forward(self, src: torch.Tensor, src_mask: torch.Tensor = None):
        x = self.embedding(src) * math.sqrt(self.d_model)
        x = self.positional_encoding(x)
        x = self.dropout(x)

        attn_weights_all = []
        for layer in self.layers:
            x, attn_weights = layer(x, src_mask)
            attn_weights_all.append(attn_weights)

        return x, attn_weights_all


class Decoder(nn.Module):
    def __init__(
        self,
        vocab_size: int,
        d_model: int,
        n_heads: int,
        num_layers: int,
        d_ff: int,
        max_len: int,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.positional_encoding = PositionalEncoding(d_model, max_len, dropout)
        self.dropout = nn.Dropout(dropout)

        self.layers = nn.ModuleList(
            [DecoderLayer(d_model, n_heads, d_ff, dropout) for _ in range(num_layers)]
        )

        self.d_model = d_model

    def forward(
        self,
        tgt: torch.Tensor,
        enc_output: torch.Tensor,
        tgt_mask: torch.Tensor = None,
        src_mask: torch.Tensor = None,
    ):
        x = self.embedding(tgt) * math.sqrt(self.d_model)
        x = self.positional_encoding(x)
        x = self.dropout(x)

        self_attn_all = []
        cross_attn_all = []

        for layer in self.layers:
            x, self_attn, cross_attn = layer(x, enc_output, tgt_mask, src_mask)
            self_attn_all.append(self_attn)
            cross_attn_all.append(cross_attn)

        return x, self_attn_all, cross_attn_all


class Transformer(nn.Module):
    def __init__(
        self,
        src_vocab_size: int,
        tgt_vocab_size: int,
        d_model: int = 256,
        n_heads: int = 8,
        num_encoder_layers: int = 3,
        num_decoder_layers: int = 3,
        d_ff: int = 512,
        max_len: int = 256,
        dropout: float = 0.1,
        pad_idx: int = 0,
    ):
        super().__init__()

        self.encoder = Encoder(
            vocab_size=src_vocab_size,
            d_model=d_model,
            n_heads=n_heads,
            num_layers=num_encoder_layers,
            d_ff=d_ff,
            max_len=max_len,
            dropout=dropout,
        )

        self.decoder = Decoder(
            vocab_size=tgt_vocab_size,
            d_model=d_model,
            n_heads=n_heads,
            num_layers=num_decoder_layers,
            d_ff=d_ff,
            max_len=max_len,
            dropout=dropout,
        )

        self.fc_out = nn.Linear(d_model, tgt_vocab_size)
        self.pad_idx = pad_idx

    def make_src_mask(self, src: torch.Tensor) -> torch.Tensor:
        """
        src: [B, src_len]
        return: [B, 1, 1, src_len]
        """
        return (src != self.pad_idx).unsqueeze(1).unsqueeze(2)

    def make_tgt_mask(self, tgt: torch.Tensor) -> torch.Tensor:
        """
        tgt: [B, tgt_len]
        return: [B, 1, tgt_len, tgt_len]
        """
        B, tgt_len = tgt.shape

        tgt_pad_mask = (tgt != self.pad_idx).unsqueeze(1).unsqueeze(2)  # [B,1,1,L]
        causal_mask = torch.tril(
            torch.ones((tgt_len, tgt_len), device=tgt.device, dtype=torch.bool)
        ).unsqueeze(0).unsqueeze(0)  # [1,1,L,L]

        return tgt_pad_mask & causal_mask

    def forward(self, src: torch.Tensor, tgt: torch.Tensor):
        """
        src: [B, src_len]
        tgt: [B, tgt_len]
        """
        src_mask = self.make_src_mask(src)
        tgt_mask = self.make_tgt_mask(tgt)

        enc_output, enc_attn_weights = self.encoder(src, src_mask)
        dec_output, dec_self_attn, dec_cross_attn = self.decoder(
            tgt, enc_output, tgt_mask, src_mask
        )

        logits = self.fc_out(dec_output)  # [B, tgt_len, tgt_vocab_size]

        return {
            "logits": logits,
            "enc_attn_weights": enc_attn_weights,
            "dec_self_attn": dec_self_attn,
            "dec_cross_attn": dec_cross_attn,
        }


def build_model(cfg, src_vocab_size: int, tgt_vocab_size: int, pad_idx: int):
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
    )
    return model


if __name__ == "__main__":
    batch_size = 2
    src_len = 7
    tgt_len = 6
    src_vocab_size = 100
    tgt_vocab_size = 120
    pad_idx = 0

    model = Transformer(
        src_vocab_size=src_vocab_size,
        tgt_vocab_size=tgt_vocab_size,
        d_model=256,
        n_heads=8,
        num_encoder_layers=3,
        num_decoder_layers=3,
        d_ff=512,
        max_len=128,
        dropout=0.1,
        pad_idx=pad_idx,
    )

    src = torch.randint(1, src_vocab_size, (batch_size, src_len))
    tgt = torch.randint(1, tgt_vocab_size, (batch_size, tgt_len))

    out = model(src, tgt)
    print("Logits shape:", out["logits"].shape)