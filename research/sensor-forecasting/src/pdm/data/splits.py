"""Engine-level train/validation splits."""
import numpy as np
from sklearn.model_selection import GroupKFold, GroupShuffleSplit


def split_units(units, val_fraction: float = 0.2, random_state: int = 42):
    """Return row indices for a reproducible split that keeps engines intact."""
    unit_array = np.asarray(units)
    if not 0 < val_fraction < 1:
        raise ValueError("val_fraction must be between zero and one")
    splitter = GroupShuffleSplit(n_splits=1, test_size=val_fraction, random_state=random_state)
    train_idx, val_idx = next(splitter.split(np.zeros(len(unit_array)), groups=unit_array))
    return train_idx, val_idx


def group_kfold(n_splits: int = 5) -> GroupKFold:
    """Construct a GroupKFold splitter for callers to pass engine IDs as groups."""
    return GroupKFold(n_splits=n_splits)
