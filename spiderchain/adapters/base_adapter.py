"""
adapters/base_adapter.py
------------------------
Base Database Adapter — Spider Chain SDK

Defines the interface every database adapter must implement.
If you can write these 5 methods for your database,
Spider Chain works with it automatically.

Supported out of the box:
    - Supabase  (supabase_adapter.py)
    - PostgreSQL / MySQL  (postgres_adapter.py)

To add your own database, subclass BaseDBAdapter and
implement the 5 methods below. That's it.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class BaseDBAdapter(ABC):
    """
    Abstract interface for database adapters.

    Every database adapter must implement these 5 methods.
    Spider Chain calls these methods internally — you never
    need to call them directly in your application code.
    """

    @abstractmethod
    def get_row_hash(self, table: str, row_id: str) -> str:
        """
        Get the current hash of a single row.

        This is how Spider Chain reads the "fingerprint" of
        each row in each table. If the row changes, the hash
        changes, and the Spider Hash breaks.

        Args:
            table:  Table name (e.g. "wallets", "nfts")
            row_id: Primary key value of the row

        Returns:
            64-character hex hash of the row data.
            Return "0" * 64 if row doesn't exist.

        Example implementation:
            row = db.query(f"SELECT * FROM {table} WHERE id = %s", row_id)
            return sha256(json.dumps(row, sort_keys=True)).hexdigest()
        """
        pass

    @abstractmethod
    def get_table_chain(self, table: str, row_id: str) -> List[Dict]:
        """
        Get the hash history for a specific row over time.

        Used to reconstruct how a row changed across events.

        Args:
            table:  Table name
            row_id: Primary key value

        Returns:
            List of { timestamp, hash, event_type } dicts,
            ordered oldest → newest.
        """
        pass

    @abstractmethod
    def get_chain_history(
        self,
        chain_id: str,
        before_timestamp: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get Spider Hash event history for a chain.

        Args:
            chain_id:         Chain identifier (token_id, user_id, etc.)
            before_timestamp: Only return events before this time (ms)
            limit:            Max events to return

        Returns:
            List of { chain_id, spider_hash, event_type, timestamp }
            ordered newest → oldest.
        """
        pass

    @abstractmethod
    def save_chain_event(self, event: Dict) -> None:
        """
        Save a Spider Hash event to your database.

        Called by ChainSequencer after every new Spider Hash
        is calculated and anchored on-chain.

        Args:
            event: {
                "chain_id":    str,
                "spider_hash": str,
                "event_type":  str,
                "timestamp":   int,
                "metadata":    dict
            }
        """
        pass

    @abstractmethod
    def get_rows_for_event(
        self,
        table_config: List[Dict],
        event_context: Dict
    ) -> Dict[str, Dict]:
        """
        Fetch all relevant rows for a Spider Hash calculation.

        Given a list of registered tables and an event context
        (e.g. { "user_id": "0xabc", "token_id": "xyz" }),
        return the current row data from each table.

        Args:
            table_config:  List of registered table definitions
                           [{ "name": "wallets", "lookup_key": "user_id" }, ...]
            event_context: Dict of values to look up rows with
                           (e.g. { "user_id": "0xabc", "token_id": "xyz" })

        Returns:
            Dict of { table_name: row_data_dict }
        """
        pass
