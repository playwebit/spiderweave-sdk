"""
adapters/postgres_adapter.py
-----------------------------
PostgreSQL / MySQL Adapter — Spider Chain SDK

For developers using raw PostgreSQL, MySQL, or any
SQLAlchemy-compatible database.

Install dependency:
    pip install psycopg2-binary   (PostgreSQL)
    pip install pymysql           (MySQL)
    pip install sqlalchemy        (both, via SQLAlchemy)

Usage:
    from spiderchain.adapters.postgres_adapter import PostgresAdapter

    # Direct PostgreSQL
    adapter = PostgresAdapter(
        connection_string="postgresql://user:pass@host:5432/dbname"
    )

    # MySQL
    adapter = PostgresAdapter(
        connection_string="mysql+pymysql://user:pass@host:3306/dbname"
    )
"""

import hashlib
import json
import time
from typing import List, Dict, Optional

from adapters.base_adapter import BaseDBAdapter


class PostgresAdapter(BaseDBAdapter):
    """
    PostgreSQL / MySQL implementation of BaseDBAdapter.
    Uses SQLAlchemy for compatibility with both databases.
    """

    def __init__(self, connection_string: str, primary_key: str = "id"):
        """
        Args:
            connection_string: SQLAlchemy-style database URL
            primary_key:       Default primary key column name (default: "id")
        """
        try:
            from sqlalchemy import create_engine, text
            self.engine = create_engine(connection_string)
            self.text = text
        except ImportError:
            raise ImportError(
                "sqlalchemy not installed. "
                "Run: pip install sqlalchemy psycopg2-binary"
            )

        self.default_pk = primary_key

    def get_row_hash(self, table: str, row_id: str) -> str:
        """Fetch a row and return its SHA-256 hash."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    self.text(
                        f"SELECT * FROM {table} WHERE {self.default_pk} = :id LIMIT 1"
                    ),
                    {"id": row_id}
                )
                row = result.mappings().first()

                if not row:
                    return "0" * 64

                return self._hash_dict(dict(row))

        except Exception:
            return "0" * 64

    def get_table_chain(self, table: str, row_id: str) -> List[Dict]:
        """Get hash history for a row from spider_chain_events table."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    self.text(
                        """
                        SELECT * FROM spider_chain_events
                        WHERE table_name = :table AND row_id = :row_id
                        ORDER BY timestamp ASC
                        """
                    ),
                    {"table": table, "row_id": row_id}
                )
                return [dict(row) for row in result.mappings().all()]

        except Exception:
            return []

    def get_chain_history(
        self,
        chain_id: str,
        before_timestamp: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get Spider Hash event history."""
        try:
            with self.engine.connect() as conn:
                if before_timestamp:
                    result = conn.execute(
                        self.text(
                            """
                            SELECT * FROM spider_chain_events
                            WHERE chain_id = :chain_id
                            AND timestamp < :before
                            ORDER BY timestamp DESC
                            LIMIT :limit
                            """
                        ),
                        {"chain_id": chain_id, "before": before_timestamp, "limit": limit}
                    )
                else:
                    result = conn.execute(
                        self.text(
                            """
                            SELECT * FROM spider_chain_events
                            WHERE chain_id = :chain_id
                            ORDER BY timestamp DESC
                            LIMIT :limit
                            """
                        ),
                        {"chain_id": chain_id, "limit": limit}
                    )

                return [dict(row) for row in result.mappings().all()]

        except Exception:
            return []

    def save_chain_event(self, event: Dict) -> None:
        """Save a Spider Hash event to the database."""
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    self.text(
                        """
                        INSERT INTO spider_chain_events
                        (chain_id, spider_hash, event_type, timestamp, metadata)
                        VALUES (:chain_id, :spider_hash, :event_type, :timestamp, :metadata)
                        """
                    ),
                    {
                        "chain_id": event["chain_id"],
                        "spider_hash": event["spider_hash"],
                        "event_type": event["event_type"],
                        "timestamp": event["timestamp"],
                        "metadata": json.dumps(event.get("metadata", {}))
                    }
                )
                conn.commit()

        except Exception as e:
            raise RuntimeError(f"Failed to save chain event: {e}")

    def get_rows_for_event(
        self,
        table_config: List[Dict],
        event_context: Dict
    ) -> Dict[str, Dict]:
        """Fetch all relevant rows for a Spider Hash calculation."""
        rows = {}

        with self.engine.connect() as conn:
            for table_def in table_config:
                table_name = table_def["name"]
                lookup_key = table_def.get("lookup_key", self.default_pk)
                lookup_value = event_context.get(lookup_key)

                if not lookup_value:
                    rows[table_name] = {}
                    continue

                try:
                    result = conn.execute(
                        self.text(
                            f"SELECT * FROM {table_name} "
                            f"WHERE {lookup_key} = :val LIMIT 1"
                        ),
                        {"val": lookup_value}
                    )
                    row = result.mappings().first()
                    rows[table_name] = dict(row) if row else {}

                except Exception:
                    rows[table_name] = {}

        return rows

    def _hash_dict(self, data: Dict) -> str:
        """Deterministically hash a dictionary."""
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
