from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AlertDecision, ComponentType, Severity, SignalPayload


class AlertStrategy(ABC):
    severity: Severity
    channel: str

    @abstractmethod
    def build(self, signal: SignalPayload) -> AlertDecision:
        raise NotImplementedError


class RdbmsAlertStrategy(AlertStrategy):
    severity = Severity.P0
    channel = "pagerduty://db-primary"

    def build(self, signal: SignalPayload) -> AlertDecision:
        return AlertDecision(
            severity=self.severity,
            channel=self.channel,
            summary=f"Database failure detected on {signal.component_id}.",
        )


class ApiAlertStrategy(AlertStrategy):
    severity = Severity.P1
    channel = "slack://api-oncall"

    def build(self, signal: SignalPayload) -> AlertDecision:
        return AlertDecision(
            severity=self.severity,
            channel=self.channel,
            summary=f"API degradation reported by {signal.component_id}.",
        )


class McpHostAlertStrategy(AlertStrategy):
    severity = Severity.P1
    channel = "slack://mcp-hosts"

    def build(self, signal: SignalPayload) -> AlertDecision:
        return AlertDecision(
            severity=self.severity,
            channel=self.channel,
            summary=f"MCP host instability detected on {signal.component_id}.",
        )


class QueueAlertStrategy(AlertStrategy):
    severity = Severity.P1
    channel = "slack://queue-ops"

    def build(self, signal: SignalPayload) -> AlertDecision:
        return AlertDecision(
            severity=self.severity,
            channel=self.channel,
            summary=f"Async queue pressure is rising on {signal.component_id}.",
        )


class CacheAlertStrategy(AlertStrategy):
    severity = Severity.P2
    channel = "slack://cache-ops"

    def build(self, signal: SignalPayload) -> AlertDecision:
        return AlertDecision(
            severity=self.severity,
            channel=self.channel,
            summary=f"Cache layer anomalies detected on {signal.component_id}.",
        )


class NoSqlAlertStrategy(AlertStrategy):
    severity = Severity.P2
    channel = "slack://nosql-ops"

    def build(self, signal: SignalPayload) -> AlertDecision:
        return AlertDecision(
            severity=self.severity,
            channel=self.channel,
            summary=f"NoSQL persistence issues reported by {signal.component_id}.",
        )


class AlertStrategyRouter:
    def __init__(self) -> None:
        self._strategies: dict[ComponentType, AlertStrategy] = {
            ComponentType.RDBMS: RdbmsAlertStrategy(),
            ComponentType.API: ApiAlertStrategy(),
            ComponentType.MCP_HOST: McpHostAlertStrategy(),
            ComponentType.ASYNC_QUEUE: QueueAlertStrategy(),
            ComponentType.CACHE: CacheAlertStrategy(),
            ComponentType.NOSQL: NoSqlAlertStrategy(),
        }

    def decide(self, signal: SignalPayload) -> AlertDecision:
        return self._strategies[signal.component_type].build(signal)
