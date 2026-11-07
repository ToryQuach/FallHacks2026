"""
history.py - Bounded Memory Queue for Sidekick Session History
"""

import json
from typing import Any, Dict, List, Optional


class _HistoryNode:
    """Internal doubly-linked list node holding an event record."""

    def __init__(self, timestamp: str, entry: str, metadata: Optional[Dict[str, Any]] = None):
        self.timestamp = timestamp
        self.entry = entry
        self.metadata = metadata or {}
        self.prev: Optional["_HistoryNode"] = None
        self.next: Optional["_HistoryNode"] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "timestamp": self.timestamp,
            "entry": self.entry,
        }
        if self.metadata:
            data["metadata"] = self.metadata
        return data

    def to_formatted_string(self) -> str:
        return f"[{self.timestamp}] {self.entry}"


class HistoryQueue:
    """
    A fixed-capacity FIFO queue for session history.
    Evicts and deallocates the oldest node when capacity is exceeded.
    """

    def __init__(self, max_size: int = 8):
        if max_size <= 0:
            raise ValueError("max_size must be greater than 0.")
        self.max_size = max_size
        self._size = 0
        self._head: Optional[_HistoryNode] = None  # Oldest node
        self._tail: Optional[_HistoryNode] = None  # Newest node

    def append(self, timestamp: str, entry: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Appends a new event. If over capacity, deallocates the oldest node."""
        node = _HistoryNode(timestamp, entry, metadata)

        if not self._tail:
            # First element
            self._head = node
            self._tail = node
            self._size = 1
            return

        # Link to current tail
        self._tail.next = node
        node.prev = self._tail
        self._tail = node
        self._size += 1

        # Evict oldest node if exceeding capacity
        if self._size > self.max_size:
            self.pop_oldest()

    def pop_oldest(self) -> Optional[_HistoryNode]:
        """Removes, unlinks, and returns the oldest node."""
        if not self._head:
            return None

        oldest = self._head
        self._head = self._head.next

        if self._head:
            self._head.prev = None
        else:
            self._tail = None

        # Break links for complete GC deallocation
        oldest.next = None
        oldest.prev = None
        self._size -= 1
        return oldest

    def clear(self) -> None:
        """Explicitly unlinks all nodes in the queue to free references."""
        curr = self._head
        while curr:
            next_node = curr.next
            curr.prev = None
            curr.next = None
            curr = next_node
        self._head = None
        self._tail = None
        self._size = 0

    def form_json(self, as_string: bool = False, format_type: str = "strings") -> Any:
        """
        Forms the history payload ready for injection into the prompt payload.

        :param as_string: If True, returns a serialized JSON string; otherwise a Python list/dict.
        :param format_type:
            - 'strings': Returns list of formatted strings, e.g. ["['14:20:00'] Task done"]
            - 'records': Returns list of structured dicts, e.g. [{"timestamp": ..., "entry": ...}]
        """
        entries = []
        curr = self._head

        while curr:
            if format_type == "records":
                entries.append(curr.to_dict())
            else:
                entries.append(curr.to_formatted_string())
            curr = curr.next

        if as_string:
            return json.dumps(entries, indent=2)
        return entries

    def to_list(self) -> List[str]:
        """Convenience helper returning simple formatted history strings."""
        return self.form_json(as_string=False, format_type="strings")

    def __len__(self) -> int:
        return self._size

    def __del__(self) -> None:
        """Destructor to ensure complete unlinking on deallocation."""
        self.clear()

    def __enter__(self) -> "HistoryQueue":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.clear()