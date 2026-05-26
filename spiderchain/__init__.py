"""
SpiderWeave SDK
---------------
A cross-table hash architecture for tamper-proof blockchain data integrity.

Invented by: Priyanshu Chauhan / PlayWebit

Usage:
    from spiderweave import SpiderWeave
    from spiderweave.adapters.supabase_adapter import SupabaseAdapter
    from spiderweave.adapters.playwebit_adapter import PlayWebitAdapter
"""

from spiderweave.spider_chain import SpiderWeave
from spiderweave.spider_hash import SpiderHashEngine
from spiderweave.chain_sequencer import ChainSequencer
from spiderweave.exceptions import (
    SpiderWeaveError,
    TamperDetectedError,
    ChainBrokenError,
    AdapterNotConfiguredError,
    InvalidHashError,
    TableNotRegisteredError
)

__version__ = "1.0.0"
__author__ = "Priyanshu Chauhan"
__license__ = "MIT"

__all__ = [
    "SpiderWeave",
    "SpiderHashEngine",
    "ChainSequencer",
    "SpiderWeaveError",
    "TamperDetectedError",
    "ChainBrokenError",
    "AdapterNotConfiguredError",
    "InvalidHashError",
    "TableNotRegisteredError"
]
