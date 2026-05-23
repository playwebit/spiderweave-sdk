"""
spider_hash.py
--------------
Core Spider Hash Engine — Spider Chain SDK
Invented by: PlayWebit / CipherVault (2024)

This is the heart of Spider Chain. It takes hashes from multiple
database tables and mixes them into one final Spider Hash that gets
anchored on-chain. If anyone tampers with any single table, the
Spider Hash breaks — exposing the attack instantly.

No external dependencies. Pure Python.
"""

import hashlib
import json
import time
from typing import List, Dict, Optional


class SpiderHashEngine:
    """
    Mixes hashes from N tables into one Spider Hash.

    The algorithm:
        1. Collect a hash from every registered table row
        2. Collect the previous Spider Hash (chain continuity)
        3. Mix all hashes together in a fixed sequence
        4. SHA-256 the combined string → final Spider Hash

    The sequence matters. Changing any one input produces a
    completely different output — tamper detection by design.
    """

    def __init__(self):
        self.version = "1.0.0"

    def calculate_spider_hash(
        self,
        table_hashes: Dict[str, str],
        previous_hash: str,
        anchor_data: Optional[Dict] = None,
        timestamp: Optional[int] = None
    ) -> str:
        """
        Calculate a Spider Hash from multiple table hashes.

        Args:
            table_hashes: Dict of { table_name: row_hash }
                          e.g. { "nfts": "abc123...", "wallets": "def456..." }
            previous_hash: The last Spider Hash in this chain (for continuity).
                           Pass "0" * 64 for the first event.
            anchor_data:   Optional dict of extra data to lock into the hash
                           (e.g. event type, user id, transaction id)
            timestamp:     Unix timestamp in ms. Uses current time if None.

        Returns:
            64-character hex SHA-256 Spider Hash
        """
        if timestamp is None:
            timestamp = int(time.time() * 1000)

        # Step 1: Hash the anchor data if provided
        anchor_hash = "0" * 64
        if anchor_data:
            anchor_hash = self._hash_dict(anchor_data)

        # Step 2: Sort table names for deterministic ordering
        # (same tables must always produce same sequence)
        sorted_tables = sorted(table_hashes.items())

        # Step 3: Build the combined string
        # Format: anchor + previous + table1_name:hash + table2_name:hash + ...
        parts = [anchor_hash, previous_hash]
        for table_name, row_hash in sorted_tables:
            parts.append(f"{table_name}:{row_hash}")

        # Step 4: Add timestamp for uniqueness
        parts.append(str(timestamp))

        combined = "|".join(parts)

        # Step 5: Final SHA-256
        final_hash = hashlib.sha256(combined.encode()).hexdigest()
        return final_hash

    def verify_spider_hash(
        self,
        stored_hash: str,
        table_hashes: Dict[str, str],
        previous_hash: str,
        anchor_data: Optional[Dict] = None,
        timestamp: Optional[int] = None
    ) -> bool:
        """
        Verify a stored Spider Hash hasn't been tampered with.

        Recomputes the hash from current table data and compares
        to the stored hash. If they don't match — tamper detected.

        Args:
            stored_hash:   The Spider Hash stored in your blockchain
            table_hashes:  Current hashes from each table row
            previous_hash: Previous Spider Hash in the chain
            anchor_data:   Same anchor data used when hash was created
            timestamp:     Same timestamp used when hash was created

        Returns:
            True if hash is valid, False if tampered
        """
        recomputed = self.calculate_spider_hash(
            table_hashes=table_hashes,
            previous_hash=previous_hash,
            anchor_data=anchor_data,
            timestamp=timestamp
        )
        return recomputed == stored_hash

    def detect_tamper(
        self,
        stored_hash: str,
        current_table_hashes: Dict[str, str],
        original_table_hashes: Dict[str, str],
        previous_hash: str,
        anchor_data: Optional[Dict] = None,
        timestamp: Optional[int] = None
    ) -> Dict:
        """
        Detect which specific table was tampered with.

        Instead of just saying "tampered", this tells you exactly
        which table broke the chain.

        Returns:
            {
                "tampered": bool,
                "broken_tables": ["wallets", "nfts"],  # which tables changed
                "spider_hash_valid": bool
            }
        """
        result = {
            "tampered": False,
            "broken_tables": [],
            "spider_hash_valid": True
        }

        # Check each table individually
        for table_name in original_table_hashes:
            original = original_table_hashes[table_name]
            current = current_table_hashes.get(table_name, "")
            if original != current:
                result["broken_tables"].append(table_name)
                result["tampered"] = True

        # Check the overall Spider Hash
        spider_valid = self.verify_spider_hash(
            stored_hash=stored_hash,
            table_hashes=current_table_hashes,
            previous_hash=previous_hash,
            anchor_data=anchor_data,
            timestamp=timestamp
        )
        if not spider_valid:
            result["spider_hash_valid"] = False
            result["tampered"] = True

        return result

    def hash_row(self, row_data: Dict) -> str:
        """
        Hash a single database row deterministically.

        Args:
            row_data: Dict of column: value pairs

        Returns:
            64-character hex SHA-256 hash of the row
        """
        return self._hash_dict(row_data)

    def _hash_dict(self, data: Dict) -> str:
        """Internal: deterministically hash a dictionary."""
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
