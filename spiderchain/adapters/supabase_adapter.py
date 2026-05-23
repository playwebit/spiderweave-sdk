"""
adapters/supabase_adapter.py
-----------------------------
Supabase Database Adapter — Spider Chain SDK

Ready-to-use adapter for Supabase (PostgreSQL under the hood).
This is what PlayWebit / CipherVault uses.

Install dependency:
    pip install supabase

Usage:
    from spiderchain.adapters.supabase_adapter import SupabaseAdapter
    adapter = SupabaseAdapter(url="https://xxx.supabase.co", key="your-anon-key")
"""

import hashlib
import json
import time
from typing import List, Dict, Optional

from adapters.base_adapter import BaseDBAdapter


class SupabaseAdapter(BaseDBAdapter):
    """
    Supabase implementation of BaseDBAdapter.

    Works with any Supabase project out of the box.
    Just pass your project URL and anon key.
    """

    def __init__(self, url: str, key: str):
        """
        Args:
            url: Your Supabase project URL
                 e.g. "https://abcdef.supabase.co"
            key: Your Supabase anon or service key
        """
        try:
            from supabase import create_client
            self.client = create_client(url, key)
        except ImportError:
            raise ImportError(
                "supabase package not installed. "
                "Run: pip install supabase"
            )

        self.url = url
        self._hash_cache = {}

    def get_row_hash(self, table: str, row_id: str) -> str:
        """Fetch a row from Supabase and return its SHA-256 hash."""
        try:
            response = self.client.table(table).select("*").eq(
                "id", row_id
            ).limit(1).execute()

            if not response.data:
                return "0" * 64

            row = response.data[0]
            return self._hash_dict(row)

        except Exception as e:
            return "0" * 64

    def get_table_chain(self, table: str, row_id: str) -> List[Dict]:
        """
        Get hash history for a row.
        Assumes your table has a spider_chain_events table or
        tracks history via insert-only pattern (like PlayWebit does).
        """
        try:
            response = self.client.table("spider_chain_events") \
                .select("*") \
                .eq("table_name", table) \
                .eq("row_id", row_id) \
                .order("timestamp", desc=False) \
                .execute()

            return response.data or []

        except Exception:
            return []

    def get_chain_history(
        self,
        chain_id: str,
        before_timestamp: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get Spider Hash event history from Supabase."""
        try:
            query = self.client.table("spider_chain_events") \
                .select("*") \
                .eq("chain_id", chain_id) \
                .order("timestamp", desc=True) \
                .limit(limit)

            if before_timestamp:
                query = query.lt("timestamp", before_timestamp)

            response = query.execute()
            return response.data or []

        except Exception:
            return []

    def save_chain_event(self, event: Dict) -> None:
        """Save a Spider Hash event to Supabase."""
        try:
            self.client.table("spider_chain_events").insert(event).execute()
        except Exception as e:
            raise RuntimeError(f"Failed to save chain event: {e}")

    def get_rows_for_event(
        self,
        table_config: List[Dict],
        event_context: Dict
    ) -> Dict[str, Dict]:
        """
        Fetch all relevant rows for a Spider Hash calculation.

        For each registered table, looks up the row using
        the lookup_key from the event_context.
        """
        rows = {}

        for table_def in table_config:
            table_name = table_def["name"]
            lookup_key = table_def.get("lookup_key", "id")
            lookup_value = event_context.get(lookup_key)

            if not lookup_value:
                rows[table_name] = {}
                continue

            try:
                response = self.client.table(table_name) \
                    .select("*") \
                    .eq(lookup_key, lookup_value) \
                    .limit(1) \
                    .execute()

                rows[table_name] = response.data[0] if response.data else {}

            except Exception:
                rows[table_name] = {}

        return rows

    def _hash_dict(self, data: Dict) -> str:
        """Deterministically hash a dictionary."""
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
