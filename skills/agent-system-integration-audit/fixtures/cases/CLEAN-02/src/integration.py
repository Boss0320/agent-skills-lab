from __future__ import annotations

import json
from pathlib import Path

from src.component import normalized_observation
from src.contracts import Decision, DrawdownRule


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "system.json"


def load_rule(config: object) -> DrawdownRule:
    if not isinstance(config, dict) or set(config) != {"threshold", "threshold_basis"}:
        raise ValueError("policy configuration must be closed")
    threshold = config["threshold"]
    basis = config["threshold_basis"]
    if not isinstance(threshold, float) or isinstance(threshold, bool) or threshold <= 0:
        raise ValueError("threshold must be a positive float")
    if basis != "percent":
        raise ValueError("threshold basis must be percent")
    return {"threshold": threshold, "threshold_basis": basis}


def evaluate_account(account_id: str) -> Decision:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    rule = load_rule(config)
    observation = normalized_observation(account_id)
    threshold_ratio = rule["threshold"] / 100
    return "BLOCK" if observation["drawdown"] >= threshold_ratio else "ALLOW"
