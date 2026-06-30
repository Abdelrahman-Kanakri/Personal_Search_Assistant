---
name: pytorch-training
description: Use when the user wants to train, fine-tune, or write a training loop for a neural network in PyTorch — including Dataset/DataLoader setup, GPU training, mixed precision, or checkpointing. Triggers "train a neural net", "pytorch training loop", "fine-tune a model", "DataLoader". NOT for classical ML (use ml-experiment).
---

# Skill: PyTorch Training Loop

Build it in this order: Dataset -> DataLoader -> model -> loop -> checkpoint.

## Non-negotiables
- One **device** variable, used everywhere. Move model AND every batch to it.
- A real **validation split** evaluated each epoch under `torch.no_grad()` +
  `model.eval()`. Switch back to `model.train()` before the next epoch.
- **Checkpoint the best val metric**, not the last epoch.
- Set seeds (`torch.manual_seed`, `np.random.seed`, `random.seed`).

## RTX 3060 (12 GB) memory tips
- Turn on **mixed precision** (AMP) — usually ~free memory + speed on Ampere.
- If you OOM: lower `batch_size`, then use **gradient accumulation** to keep the
  effective batch large. Set `num_workers` to ~your core count, `pin_memory=True`.

## Skeleton
```python
import torch
from torch.utils.data import DataLoader

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)
optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4)
scaler = torch.amp.GradScaler("cuda")            # AMP
loss_fn = torch.nn.CrossEntropyLoss()

def run_epoch(loader: DataLoader, train: bool) -> float:
    model.train(train)
    total = 0.0
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        with torch.set_grad_enabled(train), torch.amp.autocast("cuda"):
            out = model(x)
            loss = loss_fn(out, y)
        if train:
            optimizer.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        total += loss.item() * x.size(0)
    return total / len(loader.dataset)

best_val = float("inf")
for epoch in range(epochs):
    train_loss = run_epoch(train_loader, train=True)
    with torch.no_grad():
        val_loss = run_epoch(val_loader, train=False)
    print(f"epoch {epoch}: train {train_loss:.4f} | val {val_loss:.4f}")
    if val_loss < best_val:                       # checkpoint best, not last
        best_val = val_loss
        torch.save(model.state_dict(), "best.pt")
```

Install: `uv add torch`. Always report the train/val gap — a widening gap is
overfitting; both flat-and-high means underfitting or a bug (see model-eval).
