"""
OrderedEmitQueue
Ensures groups are emitted to TempSectionAssembler strictly in order (A -> B -> C ...)
without duplicating analysis logic. It buffers completed image indices per group and
only emits the next sequential group when it is complete.
"""

import threading
from typing import Callable, Dict, Set


class OrderedEmitQueue:
    def __init__(self, group_size: int,
                 emit_fn: Callable[[int], None]):
        self._group_size = max(1, int(group_size))
        self._emit_fn = emit_fn  # function(image_index) -> None
        self._lock = threading.RLock()
        self._next_group = 0
        self._buckets: Dict[int, Set[int]] = {}

    def reset(self, group_size: int) -> None:
        with self._lock:
            self._group_size = max(1, int(group_size))
            self._next_group = 0
            self._buckets.clear()

    def register(self, group_idx: int, image_index: int) -> None:
        """Register a finished image into its group bucket and emit in order."""
        with self._lock:
            bucket = self._buckets.get(group_idx)
            if bucket is None:
                bucket = set()
                self._buckets[group_idx] = bucket
            bucket.add(image_index)

            # Emit sequential groups while the next bucket is complete
            while True:
                next_bucket = self._buckets.get(self._next_group)
                if not next_bucket or len(next_bucket) < self._group_size:
                    break
                # Emit this group (stable order by image_index)
                for idx in sorted(next_bucket):
                    self._emit_fn(idx)
                del self._buckets[self._next_group]
                self._next_group += 1


