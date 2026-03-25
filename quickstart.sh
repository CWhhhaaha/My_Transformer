#!/bin/bash
# Quick Start Script for Transformer Machine Translation Project
# Run this script to train, evaluate, and test the model

set -e  # Exit on error

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Check environment
print_header "1. Checking Environment"

# Check if conda is available
if ! command -v conda &> /dev/null; then
    print_error "conda not found. Please install conda first."
    exit 1
fi
print_success "conda is available"

# Check if transformer_mt environment exists
if ! conda env list | grep -q "transformer_mt"; then
    print_error "transformer_mt environment not found"
    print_info "Creating environment from environment.yml..."
    conda env create -f environment.yml
else
    print_success "transformer_mt environment found"
fi

# Activate environment
print_info "Activating transformer_mt environment..."
eval "$(conda shell.bash hook)"
conda activate transformer_mt
print_success "Environment activated"

# Check Python version
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
print_success "Python version: $PYTHON_VERSION"

# Check PyTorch
TORCH_VERSION=$(python -c "import torch; print(torch.__version__)" 2>&1)
print_success "PyTorch version: $TORCH_VERSION"

# Check device
DEVICE=$(python -c "import torch; print('MPS' if torch.backends.mps.is_available() else 'CUDA' if torch.cuda.is_available() else 'CPU')" 2>&1)
print_success "Device: $DEVICE"

# Step 1: Prepare data
print_header "2. Preparing Dataset"

if [ ! -f "data/train.de" ] || [ ! -f "data/train.en" ]; then
    print_info "Preparing WMT14 sample dataset..."
    python download_dataset.py
    print_success "Dataset prepared"
else
    print_success "Dataset already exists"
fi

# Step 2: Run tests
print_header "3. Running Tests"
print_info "Running comprehensive test suite..."
python test_complete.py
print_success "All tests passed!"

# Step 3: Train model
print_header "4. Training Model"

if [ -f "checkpoints/best_model.pt" ]; then
    read -p "Model checkpoint already exists. Skip training? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Skipping training"
    else
        print_info "Starting training..."
        python train.py
    fi
else
    print_info "Starting training (this may take 1-2 minutes)..."
    python train.py
fi
print_success "Training completed"

# Step 4: Evaluate
print_header "5. Evaluating Model"
print_info "Running evaluation with BLEU calculation and attention visualization..."
python evaluate.py
print_success "Evaluation completed"

# Step 5: Show results
print_header "6. Results Summary"

if [ -f "checkpoints/best_model.pt" ]; then
    MODEL_SIZE=$(ls -lh checkpoints/best_model.pt | awk '{print $5}')
    echo -e "Model saved at: ${BLUE}checkpoints/best_model.pt${NC} (${BLUE}$MODEL_SIZE${NC})"
fi

if [ -f "outputs/loss_curve.png" ]; then
    echo -e "Loss curve saved at: ${BLUE}outputs/loss_curve.png${NC}"
fi

echo -e "\n${BLUE}Attention Visualizations Generated:${NC}"
ls -1 outputs/*.png 2>/dev/null | while read file; do
    filename=$(basename "$file")
    size=$(ls -lh "$file" | awk '{print $5}')
    echo -e "  • ${GREEN}$filename${NC} ($size)"
done

# Step 6: Inference
print_header "7. Quick Inference Test"
print_info "Testing interactive translation..."

python -c "
from config import Config
from data import get_dataloader
from model import build_model
from utils import load_checkpoint, set_seed
from inference import translate

cfg = Config()
set_seed(cfg.seed)
device = cfg.device

train_loader, src_vocab, tgt_vocab = get_dataloader(cfg, split='train')
model = build_model(cfg, len(src_vocab), len(tgt_vocab), src_vocab.stoi[cfg.pad_token]).to(device)
load_checkpoint(model, None, cfg.best_checkpoint_path, device)

test_sentences = [
    'guten morgen .',
    'wie geht es ?',
    'danke schön .',
]

print('\\n${BLUE}Sample Translations:${NC}')
for src_text in test_sentences:
    result = translate(src_text, model, src_vocab, tgt_vocab, cfg, device, use_beam=True)
    print(f'  Input:  ${BLUE}{src_text}${NC}')
    print(f'  Output: ${GREEN}{result}${NC}')
    print()
"

# Step 7: Show next steps
print_header "8. Next Steps"

echo -e "${YELLOW}✓ Training & Evaluation Complete!${NC}\n"

echo "Try the following:"
echo ""
echo "  1. Interactive Translation:"
echo -e "     ${BLUE}python inference.py${NC}"
echo ""
echo "  2. Modify model configuration:"
echo -e "     ${BLUE}vim config.py${NC}"
echo ""
echo "  3. Re-train with new parameters:"
echo -e "     ${BLUE}python train.py${NC}"
echo ""
echo "  4. View documentation:"
echo -e "     ${BLUE}cat README.md${NC}"
echo -e "     ${BLUE}cat USAGE_GUIDE_CN.md${NC}"
echo ""
echo "  5. Clean up old checkpoints:"
echo -e "     ${BLUE}rm checkpoints/model_epoch_*.pt${NC}"
echo ""

print_header "Project Complete! 🎉"

print_success "All steps completed successfully!"
print_success "Run 'python inference.py' to start translating!"
