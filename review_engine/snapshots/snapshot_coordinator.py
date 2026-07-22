"""Explicit snapshot service; deliberately not part of EventCollector."""
from typing import Mapping, Sequence
from .trade_snapshot_builder import TradeSnapshotBuilder
from .snapshot_repository import SnapshotRepository, SnapshotWriteResult
class SnapshotCoordinator:
 def __init__(self,builder:TradeSnapshotBuilder,repository:SnapshotRepository): self._builder,self._repository=builder,repository
 def create_for_closed_trade(self,events:Sequence[Mapping[str,object]])->SnapshotWriteResult: return self._repository.save(self._builder.build(events))
