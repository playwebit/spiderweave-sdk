"""
exceptions.py
-------------
Spider Chain SDK — Custom Exceptions

Clean, descriptive errors so developers know exactly
what went wrong and where.
"""


class SpiderChainError(Exception):
    """Base exception for all Spider Chain errors."""
    pass


class TamperDetectedError(SpiderChainError):
    """
    Raised when tampering is detected in a Spider Chain.

    This means one or more database rows have been modified
    after the Spider Hash was anchored on-chain.
    """
    def __init__(self, chain_id: str, broken_at=None, broken_hash=None):
        self.chain_id = chain_id
        self.broken_at = broken_at
        self.broken_hash = broken_hash
        super().__init__(
            f"Tamper detected in chain '{chain_id}'. "
            f"Chain broken at event index {broken_at}. "
            f"Compromised hash: {broken_hash}"
        )


class ChainBrokenError(SpiderChainError):
    """
    Raised when the Spider Hash chain sequence is broken.

    This means events are missing or have been reordered
    in the chain history.
    """
    def __init__(self, chain_id: str, expected_hash: str, found_hash: str):
        self.chain_id = chain_id
        self.expected_hash = expected_hash
        self.found_hash = found_hash
        super().__init__(
            f"Chain sequence broken for '{chain_id}'. "
            f"Expected previous hash: {expected_hash[:16]}... "
            f"Found: {found_hash[:16]}..."
        )


class AdapterNotConfiguredError(SpiderChainError):
    """
    Raised when a required adapter is missing.

    e.g. calling anchor() without a blockchain adapter,
    or calling create_spider_hash() without registering any tables.
    """
    pass


class InvalidHashError(SpiderChainError):
    """
    Raised when a hash value is invalid or malformed.
    """
    def __init__(self, hash_value: str):
        super().__init__(
            f"Invalid hash value: '{hash_value}'. "
            f"Expected 64-character hex string."
        )


class TableNotRegisteredError(SpiderChainError):
    """
    Raised when trying to use a table that hasn't been registered.
    """
    def __init__(self, table_name: str):
        super().__init__(
            f"Table '{table_name}' is not registered. "
            f"Call register_table('{table_name}') first."
        )
