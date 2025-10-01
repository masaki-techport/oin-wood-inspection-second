"""
Thread-safe in-memory image preview cache for presentation images.
Stores small JPEG bytes keyed by image_index.
"""

from __future__ import annotations

import threading
import time
from typing import Optional, Dict


class _MemoryImageCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: Dict[int, bytes] = {}
        self._last_access: Dict[int, float] = {}
        self._max_items = 2000  # reasonable upper bound

    def put_preview(self, image_index: int, jpeg_bytes: bytes) -> None:
        with self._lock:
            # Evict least recently used if over capacity
            if len(self._data) >= self._max_items:
                # Find oldest access
                oldest_key = min(self._last_access, key=self._last_access.get, default=None)
                if oldest_key is not None:
                    self._data.pop(oldest_key, None)
                    self._last_access.pop(oldest_key, None)
            self._data[image_index] = jpeg_bytes
            self._last_access[image_index] = time.time()

    def get_preview(self, image_index: int) -> Optional[bytes]:
        with self._lock:
            data = self._data.get(image_index)
            if data is not None:
                self._last_access[image_index] = time.time()
            return data

    def remove(self, image_index: int) -> None:
        with self._lock:
            self._data.pop(image_index, None)
            self._last_access.pop(image_index, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._last_access.clear()


memory_image_cache = _MemoryImageCache()


def put_preview(image_index: int, jpeg_bytes: bytes) -> None:
    memory_image_cache.put_preview(image_index, jpeg_bytes)


def get_preview(image_index: int) -> Optional[bytes]:
    return memory_image_cache.get_preview(image_index)


def remove_preview(image_index: int) -> None:
    memory_image_cache.remove(image_index)


def clear_all() -> None:
    memory_image_cache.clear()


