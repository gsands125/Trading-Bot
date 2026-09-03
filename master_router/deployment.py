from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Set


@dataclass(frozen=True)
class DeploymentGuardrails:
    paper_mode: bool
    allowed_strategies: Set[str]
    status_secret: str | None = None

    def validate_startup(self, state_path: str, accounts_config_path: str) -> list[str]:
        problems = []

        if not self.paper_mode:
            problems.append(
                "PAPER_MODE must be true for Phase 3 forward-paper deployment"
            )

        if not self.allowed_strategies:
            problems.append("at least one allowed strategy is required")

        known = {"S1", "S2", "S3", "S4"}
        unknown = sorted(self.allowed_strategies - known)
        if unknown:
            problems.append(f"unknown allowed strategies: {unknown}")

        state_parent = Path(state_path).expanduser().resolve().parent
        try:
            state_parent.mkdir(parents=True, exist_ok=True)
            probe = state_parent / ".router_write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except Exception as e:
            problems.append(f"state directory is not writable: {state_parent}: {e}")

        if not Path(accounts_config_path).exists() and not Path(state_path).exists():
            problems.append(
                "accounts config is missing and no persisted state exists"
            )

        return problems

    def strategy_allowed(self, strategy: str) -> bool:
        return strategy in self.allowed_strategies
