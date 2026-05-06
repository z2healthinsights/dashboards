"""Lazy in-process data loading helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from functools import lru_cache
from typing import Any

import pandas as pd


class LazyFrame:
    """DataFrame proxy that loads once on first use.

    The dashboard modules need to import up front so their callbacks are
    registered before Dash starts. This proxy keeps those imports cheap while
    preserving the existing in-memory pandas workflow once a page is visited.
    """

    def __init__(self, loader: Callable[[], pd.DataFrame]):
        self._load = lru_cache(maxsize=1)(loader)

    def frame(self) -> pd.DataFrame:
        return self._load()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.frame(), name)

    def __getitem__(self, key: Any) -> Any:
        return self.frame().__getitem__(key)

    def __contains__(self, key: object) -> bool:
        return key in self.frame()

    def __iter__(self) -> Iterator:
        return iter(self.frame())

    def __len__(self) -> int:
        return len(self.frame())

    def __repr__(self) -> str:
        return repr(self.frame())
