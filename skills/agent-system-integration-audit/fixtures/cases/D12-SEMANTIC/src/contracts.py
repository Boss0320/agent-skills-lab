from __future__ import annotations

from typing import Literal, TypedDict


AccountStatus = Literal["active", "paused"]
DrawdownBasis = Literal["ratio"]
ThresholdBasis = Literal["percent"]
Decision = Literal["ALLOW", "BLOCK"]

class AccountIdentity(TypedDict):
    account_id: str
    status: AccountStatus

class AccountBalance(TypedDict):
    account_id: str
    currency: Literal["USD"]
    opening_balance: float
    current_balance: float

class EquityPoint(TypedDict):
    account_id: str
    sequence: int
    equity: float

class DrawdownWindow(TypedDict):
    account_id: str
    peak_equity: float
    current_equity: float

class DrawdownObservation(TypedDict):
    account_id: str
    drawdown: float
    drawdown_basis: DrawdownBasis

class RawPolicyConfig(TypedDict):
    threshold: float
    threshold_basis: ThresholdBasis

class PolicyMetadata(TypedDict):
    policy_name: str
    policy_version: str
    owner: str


class PolicyEnvelope(TypedDict):
    metadata: PolicyMetadata
    rule: RawPolicyConfig


class EvaluationContext(TypedDict):
    account: AccountIdentity
    observation: DrawdownObservation


class EvaluationResult(TypedDict):
    account_id: str
    decision: Decision
    observed_drawdown: float
    applied_threshold: float


class AuditEvent(TypedDict):
    account_id: str
    policy_version: str
    decision: Decision


class AccountSnapshot(TypedDict):
    identity: AccountIdentity
    balance: AccountBalance
    latest_equity: EquityPoint


class PolicySelection(TypedDict):
    account_id: str
    policy_name: str
    policy_version: str


class EvaluationRequest(TypedDict):
    snapshot: AccountSnapshot
    policy: PolicySelection


class EvaluationResponse(TypedDict):
    result: EvaluationResult
    event: AuditEvent


class PolicyLimits(TypedDict):
    minimum_threshold: float
    maximum_threshold: float


class PolicyRegistryEntry(TypedDict):
    name: str
    version: str
    limits: PolicyLimits


class ValidationResult(TypedDict):
    accepted: bool
    message: str


class RuleSource(TypedDict):
    source_name: str
    loaded_at: str


class RuleDocument(TypedDict):
    source: RuleSource
    policy: PolicyEnvelope


class DrawdownRule(TypedDict):
    """Validated limit supplied by the policy configuration boundary."""

    threshold: float
    threshold_basis: Literal["percent"]
