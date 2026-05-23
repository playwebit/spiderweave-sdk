"""
spider_chain.py
---------------
SpiderChain — Main SDK Class

This is the only class developers need to import.
Everything else is wired up internally.

Basic usage:
    from spiderchain import SpiderChain
    from spiderchain.adapters.supabase_adapter import SupabaseAdapter
    from spiderchain.adapters.playwebit_adapter import PlayWebitAdapter

    sc = SpiderChain(
        db_adapter=SupabaseAdapter(url="...", key="..."),
        blockchain_adapter=PlayWebitAdapter(node_url="...")
    )

    sc.register_table("nfts",        lookup_key="token_id")
    sc.register_table("wallets",     lookup_key="user_id")
    sc.register_table("sessions",    lookup_key="user_id")
    sc.register_table("marketplace", lookup_key="token_id")

    result = sc.create_and_anchor(
        chain_id="token_abc123",
        event_type="mint",
        event_context={"token_id": "abc123", "user_id": "0xabc"}
    )
"""

import time
from typing import Dict, List, Optional

from spider_hash import SpiderHashEngine
from chain_sequencer import ChainSequencer
from adapters.base_adapter import BaseDBAdapter
from adapters.base_blockchain_adapter import BaseBlockchainAdapter
from exceptions import (
    TamperDetectedError,
    ChainBrokenError,
    AdapterNotConfiguredError
)


class SpiderChain:
    """
    Main Spider Chain SDK class.

    Orchestrates the full Spider Hash lifecycle:
        1. Fetch rows from all registered tables
        2. Hash each row
        3. Mix hashes into one Spider Hash
        4. Anchor Spider Hash on-chain
        5. Record event in chain history

    Works with any database and any blockchain via adapters.
    """

    def __init__(
        self,
        db_adapter: BaseDBAdapter,
        blockchain_adapter: Optional[BaseBlockchainAdapter] = None
    ):
        """
        Args:
            db_adapter:         Any BaseDBAdapter implementation
                                (SupabaseAdapter, PostgresAdapter, or custom)
            blockchain_adapter: Any BaseBlockchainAdapter implementation
                                (PlayWebitAdapter, EVMAdapter, or custom)
                                Optional — you can calculate hashes without anchoring.
        """
        self.db = db_adapter
        self.blockchain = blockchain_adapter
        self.hash_engine = SpiderHashEngine()
        self.sequencer = ChainSequencer(db_adapter=db_adapter)
        self._tables: List[Dict] = []

    def register_table(
        self,
        table_name: str,
        lookup_key: str = "id",
        is_anchor: bool = False
    ) -> "SpiderChain":
        """
        Register a database table to participate in Spider Hash calculation.

        Call this for every table whose rows should be included
        in the Spider Hash. Order of registration matters —
        tables are hashed in registration order.

        Args:
            table_name: Name of the database table
            lookup_key: Column name used to look up the relevant row
                        e.g. "user_id", "token_id", "order_id"
            is_anchor:  If True, this table's data is used as the
                        primary anchor data (locked into the hash header)

        Returns:
            self — allows chaining: sc.register_table(...).register_table(...)
        """
        self._tables.append({
            "name": table_name,
            "lookup_key": lookup_key,
            "is_anchor": is_anchor
        })
        return self

    def create_spider_hash(
        self,
        chain_id: str,
        event_context: Dict,
        timestamp: Optional[int] = None
    ) -> Dict:
        """
        Calculate a Spider Hash without anchoring it.

        Useful for verification, testing, or when you want
        to anchor manually later.

        Args:
            chain_id:      Identifier for this chain
            event_context: Dict of lookup values
                           e.g. { "token_id": "abc", "user_id": "0xabc" }
            timestamp:     Unix ms timestamp (uses current time if None)

        Returns:
            {
                "spider_hash": str,
                "table_hashes": { table_name: hash },
                "previous_hash": str,
                "timestamp": int
            }
        """
        if not self._tables:
            raise AdapterNotConfiguredError(
                "No tables registered. Call register_table() first."
            )

        if timestamp is None:
            timestamp = int(time.time() * 1000)

        rows = self.db.get_rows_for_event(
            table_config=self._tables,
            event_context=event_context
        )

        table_hashes = {}
        anchor_data = {}

        for table_def in self._tables:
            name = table_def["name"]
            row = rows.get(name, {})
            table_hashes[name] = self.hash_engine.hash_row(row)

            if table_def.get("is_anchor"):
                anchor_data.update(row)

        previous_hash = self.sequencer.get_previous_hash(
            chain_id=chain_id,
            before_timestamp=timestamp
        )

        spider_hash = self.hash_engine.calculate_spider_hash(
            table_hashes=table_hashes,
            previous_hash=previous_hash,
            anchor_data=anchor_data if anchor_data else None,
            timestamp=timestamp
        )

        return {
            "spider_hash": spider_hash,
            "table_hashes": table_hashes,
            "previous_hash": previous_hash,
            "timestamp": timestamp
        }

    def anchor(
        self,
        spider_hash: str,
        chain_id: str,
        event_type: str,
        metadata: Optional[Dict] = None,
        timestamp: Optional[int] = None
    ) -> Dict:
        """
        Anchor an existing Spider Hash on-chain.

        Args:
            spider_hash: Hash to anchor (from create_spider_hash)
            chain_id:    Chain identifier
            event_type:  Event label ("mint", "transfer", "update", etc.)
            metadata:    Optional extra data to store
            timestamp:   Unix ms timestamp

        Returns:
            { "tx_hash": str, "spider_hash": str, "chain_id": str }
        """
        if not self.blockchain:
            raise AdapterNotConfiguredError(
                "No blockchain adapter configured. "
                "Pass blockchain_adapter= to SpiderChain()."
            )

        if timestamp is None:
            timestamp = int(time.time() * 1000)

        tx_hash = self.blockchain.anchor_hash(
            spider_hash=spider_hash,
            chain_id=chain_id,
            event_type=event_type,
            metadata=metadata
        )

        self.sequencer.sequence_event(
            chain_id=chain_id,
            spider_hash=spider_hash,
            event_type=event_type,
            metadata=metadata,
            timestamp=timestamp
        )

        return {
            "tx_hash": tx_hash,
            "spider_hash": spider_hash,
            "chain_id": chain_id,
            "event_type": event_type,
            "timestamp": timestamp
        }

    def create_and_anchor(
        self,
        chain_id: str,
        event_type: str,
        event_context: Dict,
        metadata: Optional[Dict] = None,
        timestamp: Optional[int] = None
    ) -> Dict:
        """
        Calculate Spider Hash AND anchor it on-chain in one call.

        This is the main function most developers will use.

        Args:
            chain_id:      Chain identifier (token_id, user_id, etc.)
            event_type:    Event label ("mint", "transfer", "sale", etc.)
            event_context: Lookup values for fetching rows
            metadata:      Optional extra data
            timestamp:     Unix ms timestamp

        Returns:
            {
                "tx_hash": str,
                "spider_hash": str,
                "table_hashes": dict,
                "previous_hash": str,
                "chain_id": str,
                "event_type": str,
                "timestamp": int
            }
        """
        hash_result = self.create_spider_hash(
            chain_id=chain_id,
            event_context=event_context,
            timestamp=timestamp
        )

        anchor_result = self.anchor(
            spider_hash=hash_result["spider_hash"],
            chain_id=chain_id,
            event_type=event_type,
            metadata=metadata,
            timestamp=hash_result["timestamp"]
        )

        return {**hash_result, **anchor_result}

    def verify(
        self,
        chain_id: str,
        event_context: Dict,
        stored_hash: str,
        stored_timestamp: int
    ) -> Dict:
        """
        Verify a stored Spider Hash against current database state.

        If any table row has changed since the hash was created,
        this will return tampered=True and show which tables changed.

        Args:
            chain_id:          Chain identifier
            event_context:     Same lookup values used when hash was created
            stored_hash:       The Spider Hash stored on-chain
            stored_timestamp:  Timestamp when the hash was created

        Returns:
            {
                "valid": bool,
                "tampered": bool,
                "broken_tables": list,
                "spider_hash_valid": bool
            }
        """
        current = self.create_spider_hash(
            chain_id=chain_id,
            event_context=event_context,
            timestamp=stored_timestamp
        )

        is_valid = current["spider_hash"] == stored_hash

        return {
            "valid": is_valid,
            "tampered": not is_valid,
            "current_hash": current["spider_hash"],
            "stored_hash": stored_hash,
            "table_hashes": current["table_hashes"]
        }

    def get_chain_history(self, chain_id: str, limit: int = 50) -> List[Dict]:
        """
        Get the full event history for a chain.

        Args:
            chain_id: Chain identifier
            limit:    Max events to return

        Returns:
            List of { spider_hash, event_type, timestamp, ... }
            in chronological order
        """
        return self.sequencer.get_chain_history(
            chain_id=chain_id,
            limit=limit
        )

    def detect_tamper(self, chain_id: str, limit: int = 50) -> Dict:
        """
        Walk the chain history and detect any broken links.

        Args:
            chain_id: Chain identifier
            limit:    How many events to check

        Returns:
            {
                "tampered": bool,
                "valid": bool,
                "total_events": int,
                "broken_at": int or None
            }

        Raises:
            TamperDetectedError if tampering is found
        """
        result = self.sequencer.verify_chain_integrity(chain_id=chain_id)

        if not result["valid"]:
            raise TamperDetectedError(
                chain_id=chain_id,
                broken_at=result.get("broken_at"),
                broken_hash=result.get("broken_hash")
            )

        return result

    @property
    def registered_tables(self) -> List[str]:
        """List of currently registered table names."""
        return [t["name"] for t in self._tables]
