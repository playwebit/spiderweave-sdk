"""
chain_sequencer.py
------------------
Chain Sequencer — Spider Chain SDK

Maintains the sequential history of Spider Hashes.
Every event (mint, transfer, sale, update) produces a new
Spider Hash that links to the previous one — forming a chain.

This is what makes Spider Chain tamper-proof over time:
you can't insert or delete events without breaking the sequence.

No external dependencies. Pure Python.
"""

from typing import List, Dict, Optional
import time


class ChainSequencer:
    """
    Manages the sequence of Spider Hashes across events.

    Think of this as the "spine" of the Spider Chain.
    Each Spider Hash links to the one before it, just like
    blocks in a blockchain, but at the database-row level.
    """

    GENESIS_HASH = "0" * 64  # Starting hash for a new chain

    def __init__(self, db_adapter):
        """
        Args:
            db_adapter: Any adapter implementing BaseDBAdapter.
                        Used to read/write chain history.
        """
        self.db = db_adapter

    def get_previous_hash(
        self,
        chain_id: str,
        before_timestamp: Optional[int] = None
    ) -> str:
        """
        Get the most recent Spider Hash for a given chain.

        Args:
            chain_id:         Identifier for this chain
                              (e.g. token_id, user_id, document_id)
            before_timestamp: Only look at events before this time.
                              Used to reconstruct history accurately.

        Returns:
            The last Spider Hash, or GENESIS_HASH if chain is new.
        """
        try:
            history = self.db.get_chain_history(
                chain_id=chain_id,
                before_timestamp=before_timestamp,
                limit=1
            )
            if history:
                return history[0].get("spider_hash", self.GENESIS_HASH)
            return self.GENESIS_HASH
        except Exception:
            return self.GENESIS_HASH

    def get_chain_history(
        self,
        chain_id: str,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get the full event history for a chain.

        Returns a list of events in chronological order,
        each containing the Spider Hash at that point in time.

        Args:
            chain_id: Identifier for this chain
            limit:    Max number of events to return

        Returns:
            List of { timestamp, spider_hash, event_type, ... }
        """
        return self.db.get_chain_history(
            chain_id=chain_id,
            limit=limit
        )

    def sequence_event(
        self,
        chain_id: str,
        spider_hash: str,
        event_type: str,
        metadata: Optional[Dict] = None,
        timestamp: Optional[int] = None
    ) -> Dict:
        """
        Record a new event in the chain sequence.

        Called after a Spider Hash is calculated and anchored.
        Stores the event so future hashes can chain off it.

        Args:
            chain_id:   Identifier for this chain
            spider_hash: The Spider Hash just calculated
            event_type:  Human-readable event label
                         (e.g. "mint", "transfer", "sale", "update")
            metadata:    Optional extra data to store with the event
            timestamp:   Unix ms timestamp (uses current time if None)

        Returns:
            The saved event record
        """
        if timestamp is None:
            timestamp = int(time.time() * 1000)

        event = {
            "chain_id": chain_id,
            "spider_hash": spider_hash,
            "event_type": event_type,
            "timestamp": timestamp,
            "metadata": metadata or {}
        }

        self.db.save_chain_event(event)
        return event

    def verify_chain_integrity(self, chain_id: str) -> Dict:
        """
        Walk the entire chain history and verify every link.

        Checks that each event's previous_hash matches the
        actual hash of the event before it. Finds broken links.

        Args:
            chain_id: Identifier for this chain

        Returns:
            {
                "valid": bool,
                "total_events": int,
                "broken_at": event_index or None,
                "broken_hash": hash_value or None
            }
        """
        history = self.db.get_chain_history(chain_id=chain_id, limit=10000)

        result = {
            "valid": True,
            "total_events": len(history),
            "broken_at": None,
            "broken_hash": None
        }

        if len(history) < 2:
            return result

        for i in range(1, len(history)):
            expected_previous = history[i - 1]["spider_hash"]
            actual_previous = history[i].get("previous_hash", "")

            if expected_previous != actual_previous:
                result["valid"] = False
                result["broken_at"] = i
                result["broken_hash"] = history[i]["spider_hash"]
                break

        return result
