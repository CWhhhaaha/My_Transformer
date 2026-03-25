from dataclasses import dataclass, field
from pathlib import Path
import torch


@dataclass
class Config:
    """
    Project configuration for a small Transformer machine translation project.
    Assumed dataset format:

    data/
        train.de
        train.en
        valid.de
        valid.en
        test.de
        test.en
    """

    # ----------------------------
    # Paths
    # ----------------------------
    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parent)
    data_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent / "data")
    checkpoint_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent / "checkpoints")
    output_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent / "outputs")

    train_src: Path = field(init=False)
    train_tgt: Path = field(init=False)
    valid_src: Path = field(init=False)
    valid_tgt: Path = field(init=False)
    test_src: Path = field(init=False)
    test_tgt: Path = field(init=False)

    # ----------------------------
    # Languages / tokenization
    # ----------------------------
    src_lang: str = "de"
    tgt_lang: str = "en"

    # special tokens
    pad_token: str = "<pad>"
    unk_token: str = "<unk>"
    bos_token: str = "<bos>"
    eos_token: str = "<eos>"

    # vocabulary
    min_freq: int = 2
    max_vocab_size: int = 20000

    # ----------------------------
    # Model hyperparameters
    # ----------------------------
    d_model: int = 256
    n_heads: int = 8
    num_encoder_layers: int = 3
    num_decoder_layers: int = 3
    d_ff: int = 512
    dropout: float = 0.1
    max_len: int = 256

    # ----------------------------
    # Training hyperparameters
    # ----------------------------
    batch_size: int = 32
    num_epochs: int = 15
    lr: float = 1e-4
    weight_decay: float = 1e-4
    clip_grad_norm: float = 1.0
    label_smoothing: float = 0.0

    # ----------------------------
    # Runtime
    # ----------------------------
    num_workers: int = 0   # Mac / MPS usually safer with 0
    pin_memory: bool = False
    seed: int = 42

    # ----------------------------
    # Checkpoint / logging
    # ----------------------------
    save_best_only: bool = True
    best_checkpoint_name: str = "best_model.pt"
    last_checkpoint_name: str = "last_model.pt"
    loss_curve_name: str = "loss_curve.png"

    # ----------------------------
    # Evaluation / inference
    # ----------------------------
    beam_size: int = 4
    max_decode_len: int = 50

    def __post_init__(self) -> None:
        self.train_src = self.data_dir / f"train.{self.src_lang}"
        self.train_tgt = self.data_dir / f"train.{self.tgt_lang}"

        self.valid_src = self.data_dir / f"valid.{self.src_lang}"
        self.valid_tgt = self.data_dir / f"valid.{self.tgt_lang}"

        self.test_src = self.data_dir / f"test.{self.src_lang}"
        self.test_tgt = self.data_dir / f"test.{self.tgt_lang}"

        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def device(self) -> torch.device:
        if torch.backends.mps.is_available():
            return torch.device("mps")
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")

    @property
    def best_checkpoint_path(self) -> Path:
        return self.checkpoint_dir / self.best_checkpoint_name

    @property
    def last_checkpoint_path(self) -> Path:
        return self.checkpoint_dir / self.last_checkpoint_name

    @property
    def loss_curve_path(self) -> Path:
        return self.output_dir / self.loss_curve_name

    def verify_data_files(self) -> None:
        required_files = [
            self.train_src, self.train_tgt,
            self.valid_src, self.valid_tgt,
            self.test_src, self.test_tgt,
        ]
        missing = [str(p) for p in required_files if not p.exists()]
        if missing:
            raise FileNotFoundError(
                "Missing dataset files:\n" + "\n".join(missing) +
                "\n\nExpected structure:\n"
                f"{self.data_dir}/train.{self.src_lang}\n"
                f"{self.data_dir}/train.{self.tgt_lang}\n"
                f"{self.data_dir}/valid.{self.src_lang}\n"
                f"{self.data_dir}/valid.{self.tgt_lang}\n"
                f"{self.data_dir}/test.{self.src_lang}\n"
                f"{self.data_dir}/test.{self.tgt_lang}"
            )


if __name__ == "__main__":
    cfg = Config()
    print("Project root:", cfg.project_root)
    print("Data dir:", cfg.data_dir)
    print("Device:", cfg.device)
    print("Best checkpoint:", cfg.best_checkpoint_path)
    print("Loss curve path:", cfg.loss_curve_path)