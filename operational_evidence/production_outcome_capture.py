"""PR202 post-completion integration for immutable live outcome capture.

The production host attaches this observer to its completed-trade notification.
That notification is downstream of broker confirmation, result finalization, and
the end of Executor authority.  The observer never calls back into the source.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Protocol

from runtime.execution_contract import ExecutionContext
from runtime.live_outcome_capture import (
    BrokerCompletedTrade,
    LiveOutcomeCapture,
    LiveOutcomeCaptureError,
    LiveOutcomeRecord,
)


class CompletedTradeSource(Protocol):
    """Production host boundary exposed only after its lifecycle is complete."""

    def subscribe_completed_trade(
        self, observer: Callable[[BrokerCompletedTrade], None]
    ) -> None: ...


class CaptureDisposition(str, Enum):
    CAPTURED = "CAPTURED"
    DUPLICATE_SUPPRESSED = "DUPLICATE_SUPPRESSED"
    CAPTURE_FAILED = "CAPTURE_FAILED"


@dataclass(frozen=True, slots=True)
class ProductionCaptureResult:
    """Passive observability result; never an execution result or authority."""

    disposition: CaptureDisposition
    record: LiveOutcomeRecord | None = None
    failure_code: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class ProductionOutcomeCaptureIntegration:
    """Automatically capture each notification without affecting its producer.

    Repository atomic creation remains the concurrency authority for exactly-once
    persistence.  A repeated notification is therefore acknowledged as already
    captured, while every other capture failure is contained at this boundary.
    """

    def __init__(
        self,
        source: CompletedTradeSource,
        capture: LiveOutcomeCapture,
        context: ExecutionContext,
        *,
        clock: Callable[[], str] = _utc_now,
        result_observer: Callable[[ProductionCaptureResult], None] | None = None,
    ) -> None:
        if not callable(getattr(source, "subscribe_completed_trade", None)):
            raise TypeError("COMPLETED_TRADE_SOURCE_REQUIRED")
        if type(capture) is not LiveOutcomeCapture:
            raise TypeError("LIVE_OUTCOME_CAPTURE_REQUIRED")
        if type(context) is not ExecutionContext:
            raise TypeError("EXECUTION_CONTEXT_REQUIRED")
        if not callable(clock) or (result_observer is not None and not callable(result_observer)):
            raise TypeError("INVALID_CAPTURE_OBSERVER_CONFIGURATION")

        self._capture = capture
        self._context = context
        self._clock = clock
        self._result_observer = result_observer
        # Registration is the only interaction with the production host.  No
        # broker, order, position, exit, or Executor method is available here.
        source.subscribe_completed_trade(self._after_completed_trade)

    def _after_completed_trade(self, completed: BrokerCompletedTrade) -> None:
        try:
            record = self._capture.capture(
                completed, self._context, captured_at=self._clock()
            )
            result = ProductionCaptureResult(CaptureDisposition.CAPTURED, record=record)
        except LiveOutcomeCaptureError as exc:
            code = str(exc)
            disposition = (
                CaptureDisposition.DUPLICATE_SUPPRESSED
                if code == "DUPLICATE_RECORD"
                else CaptureDisposition.CAPTURE_FAILED
            )
            result = ProductionCaptureResult(disposition, failure_code=code)
        except Exception as exc:  # containment is mandatory at the passive boundary
            result = ProductionCaptureResult(
                CaptureDisposition.CAPTURE_FAILED,
                failure_code=f"CAPTURE_INFRASTRUCTURE_FAILURE:{type(exc).__name__}",
            )

        if self._result_observer is not None:
            try:
                self._result_observer(result)
            except Exception:
                # Diagnostic consumers cannot feed failure into trade completion.
                pass


__all__ = [
    "CaptureDisposition",
    "CompletedTradeSource",
    "ProductionCaptureResult",
    "ProductionOutcomeCaptureIntegration",
]
