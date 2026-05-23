"""
utils.py
--------
Spider Chain SDK — Utility Functions

Shared helpers used across the SDK.
"""

import hashlib
import json
import time
import re
from typing import Dict, Any


def hash_dict(data: Dict) -> str:
    """
    Deterministically hash a dictionary to a 64-char hex string.

    Keys are sorted before hashing to ensure the same dict
    always produces the same hash regardless of insertion order.

    Args:
        data: Any JSON-serializable dictionary

    Returns:
        64-character SHA-256 hex string
    """
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def hash_string(value: str) -> str:
    """
    Hash a string to a 64-char hex string.

    Args:
        value: Any string

    Returns:
        64-character SHA-256 hex string
    """
    return hashlib.sha256(value.encode()).hexdigest()


def current_timestamp_ms() -> int:
    """
    Get current Unix timestamp in milliseconds.

    Returns:
        Current time as integer milliseconds since epoch
    """
    return int(time.time() * 1000)


def is_valid_hash(hash_value: str) -> bool:
    """
    Check if a string is a valid 64-character hex hash.

    Args:
        hash_value: String to validate

    Returns:
        True if valid SHA-256 hex hash, False otherwise
    """
    if not isinstance(hash_value, str):
        return False
    return bool(re.match(r'^[a-f0-9]{64}$', hash_value.lower()))


def genesis_hash() -> str:
    """
    Return the genesis hash used to start a new chain.

    Returns:
        64 zeros — the standard chain starting point
    """
    return "0" * 64


def mix_hashes(hashes: list, separator: str = "|") -> str:
    """
    Mix a list of hashes into one final hash.

    Args:
        hashes:    List of hash strings to combine
        separator: String to join hashes with (default: "|")

    Returns:
        64-character SHA-256 hash of the combined string
    """
    combined = separator.join(hashes)
    return hashlib.sha256(combined.encode()).hexdigest()


def sanitize_table_name(name: str) -> str:
    """
    Sanitize a table name to prevent SQL injection.

    Only allows alphanumeric characters and underscores.

    Args:
        name: Table name to sanitize

    Returns:
        Sanitized table name

    Raises:
        ValueError if name contains invalid characters
    """
    if not re.match(r'^[a-zA-Z0-9_]+$', name):
        raise ValueError(
            f"Invalid table name: '{name}'. "
            f"Only alphanumeric characters and underscores are allowed."
        )
    return name
