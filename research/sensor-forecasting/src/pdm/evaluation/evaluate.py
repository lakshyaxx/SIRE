"""Evaluation entry point delegated to the reproducible training runner."""
from pdm.training.train import train


def evaluate(subset: str = "FD001") -> dict:
    """Run the configured final official test evaluation."""
    return train(subset=subset, evaluate_test=True)
