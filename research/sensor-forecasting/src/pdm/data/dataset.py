"""PyTorch dataset and loader helpers for window arrays."""
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset


class WindowDataset(Dataset):
    """Tensor-backed dataset of input windows and scalar RUL targets."""
    def __init__(self, windows: np.ndarray, targets: np.ndarray) -> None:
        if len(windows) != len(targets):
            raise ValueError("windows and targets must have equal lengths")
        self.windows = torch.as_tensor(windows, dtype=torch.float32)
        self.targets = torch.as_tensor(targets, dtype=torch.float32)

    def __len__(self) -> int:
        return len(self.targets)

    def __getitem__(self, index: int):
        return self.windows[index], self.targets[index]


def make_dataloader(dataset: Dataset, batch_size: int = 128, shuffle: bool = False) -> DataLoader:
    """Build a DataLoader with a small set of explicit, stable defaults."""
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)
