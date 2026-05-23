"""
spider_hash.py
--------------
Core Spider Hash Engine — Spider Chain SDK

Supports two modes:

1. GENERIC mode (default)
   Works with any database, any tables.
   Collects row hashes and mixes them in sorted order.

2. CUSTOM STRATEGY mode
   Developer passes a HashStrategy subclass that defines
   exactly how hashes are collected and mixed.
   Used by PlayWebit's 7-component algorithm.

No external dependencies. Pure Python.
"""

import hashlib
import json
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Optional


# ── Base Strategy ─────────────────────────────────────────────

class HashStrategy(ABC):
    """
    Abstract base for custom hash strategies.

    Subclass this to define your own hash mixing logic.
    Pass an instance to SpiderHashEngine(strategy=...).

    Example — PlayWebit 7-component strategy:
        engine = SpiderHashEngine(strategy=PlayWebitStrategy(supabase_client))
    """

    @abstractmethod
    def collect_hashes(self, event_context: Dict) -> Dict[str, str]:
        """
        Collect all component hashes for this event.

        Args:
            event_context: Dict of values describing the event
                           e.g. { "token_id": "abc", "user_id": "0xabc" }

        Returns:
            Dict of { component_name: hash_value }
            e.g. {
                "original":        "a3f9...",
                "previous_nft":    "b7d4...",
                "creator_wallet":  "c9a1...",
                ...
            }
        """
        pass

    @abstractmethod
    def mix_hashes(self, hashes: Dict[str, str]) -> str:
        """
        Mix collected hashes into one final Spider Hash.

        Args:
            hashes: Dict returned by collect_hashes()

        Returns:
            64-character hex SHA-256 Spider Hash
        """
        pass


# ── PlayWebit Strategy ────────────────────────────────────────

class PlayWebitStrategy(HashStrategy):
    """
    PlayWebit / CipherVault 7-component Spider Hash Strategy.

    This is the original Spider Chain Hash Architecture as
    implemented in PlayWebit's NFT platform.

    Components:
        1. original_hash       — SHA256 of core NFT fields
        2. previous_nft_hash   — latest hash across all NFTs
        3. same_token_hash     — latest hash for this specific token
        4. creator_wallet_hash — wallet integrity_hash for creator
        5. owner_wallet_hash   — wallet integrity_hash for owner
        6. creator_session_hash— session integrity_hash for creator
        7. owner_session_hash  — session integrity_hash for owner

    Usage:
        from spiderchain.spider_hash import PlayWebitStrategy
        from supabase import create_client

        supabase = create_client(url, key)
        strategy = PlayWebitStrategy(supabase)
        engine   = SpiderHashEngine(strategy=strategy)
    """

    def __init__(self, supabase_client):
        """
        Args:
            supabase_client: An initialized Supabase client instance
        """
        self.db = supabase_client

    def collect_hashes(self, event_context: Dict) -> Dict[str, str]:
        """
        Collect all 7 components from Supabase tables.

        event_context must contain:
            nft_data:  full NFT row dict
            timestamp: broadcast timestamp in ms
        """
        nft_data  = event_context["nft_data"]
        timestamp = event_context["timestamp"]

        # 1. Original data hash
        original_data = json.dumps({
            "token_id":   nft_data["token_id"],
            "metadata":   nft_data["metadata"],
            "creator":    nft_data["creator"],
            "owner":      nft_data["owner"],
            "for_sale":   nft_data["for_sale"],
            "sale_price": nft_data["sale_price"],
            "timestamp":  nft_data["timestamp"]
        }, sort_keys=True)
        original_hash = hashlib.sha256(original_data.encode()).hexdigest()

        # 2. Previous NFT hash — latest across ALL nfts
        try:
            r = self.db.table('nfts').select('spider_hash')\
                .lt('timestamp', timestamp)\
                .order('timestamp', desc=True).limit(1).execute()
            previous_hash = r.data[0]['spider_hash'] if r.data else "0" * 64
        except:
            previous_hash = "0" * 64

        # 3. Same token audit hash — latest for THIS token
        try:
            r = self.db.table('nfts').select('spider_hash')\
                .eq('token_id', nft_data["token_id"])\
                .lt('timestamp', timestamp)\
                .order('timestamp', desc=True).limit(1).execute()
            same_token_hash = r.data[0]['spider_hash'] if r.data else "0" * 64
        except:
            same_token_hash = "0" * 64

        # 4. Creator wallet integrity hash
        try:
            r = self.db.table('wallets').select('integrity_hash')\
                .eq('address', nft_data["creator"].lower()).execute()
            creator_wallet_hash = r.data[0]['integrity_hash'] if r.data else "0" * 64
        except:
            creator_wallet_hash = "0" * 64

        # 5. Owner wallet integrity hash
        try:
            r = self.db.table('wallets').select('integrity_hash')\
                .eq('address', nft_data["owner"].lower()).execute()
            owner_wallet_hash = r.data[0]['integrity_hash'] if r.data else "0" * 64
        except:
            owner_wallet_hash = "0" * 64

        # 6. Creator session integrity hash
        try:
            r = self.db.table('sessions').select('integrity_hash')\
                .eq('address', nft_data["creator"].lower()).execute()
            creator_session_hash = r.data[0]['integrity_hash'] if r.data else "0" * 64
        except:
            creator_session_hash = "0" * 64

        # 7. Owner session integrity hash
        try:
            r = self.db.table('sessions').select('integrity_hash')\
                .eq('address', nft_data["owner"].lower()).execute()
            owner_session_hash = r.data[0]['integrity_hash'] if r.data else "0" * 64
        except:
            owner_session_hash = "0" * 64

        return {
            "1_original":        original_hash,
            "2_previous_nft":    previous_hash,
            "3_same_token":      same_token_hash,
            "4_creator_wallet":  creator_wallet_hash,
            "5_owner_wallet":    owner_wallet_hash,
            "6_creator_session": creator_session_hash,
            "7_owner_session":   owner_session_hash
        }

    def mix_hashes(self, hashes: Dict[str, str]) -> str:
        """
        Mix 7 components in exact PlayWebit order.
        Concatenate all 7 hashes then SHA256 the result.
        """
        combined = (
            hashes["1_original"] +
            hashes["2_previous_nft"] +
            hashes["3_same_token"] +
            hashes["4_creator_wallet"] +
            hashes["5_owner_wallet"] +
            hashes["6_creator_session"] +
            hashes["7_owner_session"]
        )
        return hashlib.sha256(combined.encode()).hexdigest()


# ── Generic Strategy ──────────────────────────────────────────

class GenericStrategy(HashStrategy):
    """
    Generic hash strategy — works with any database and any tables.

    Sorts table hashes alphabetically for deterministic ordering
    then mixes them with a separator. No table-specific logic.

    This is the default strategy when no custom one is provided.
    """

    def collect_hashes(self, event_context: Dict) -> Dict[str, str]:
        """
        event_context must contain:
            table_hashes: { table_name: row_hash }
            previous_hash: str
        """
        return {
            "table_hashes":  event_context.get("table_hashes", {}),
            "previous_hash": event_context.get("previous_hash", "0" * 64)
        }

    def mix_hashes(self, hashes: Dict[str, str]) -> str:
        """Mix table hashes sorted alphabetically + previous hash."""
        table_hashes  = hashes.get("table_hashes", {})
        previous_hash = hashes.get("previous_hash", "0" * 64)

        parts = [previous_hash]
        for name, h in sorted(table_hashes.items()):
            parts.append(f"{name}:{h}")

        combined = "|".join(parts)
        return hashlib.sha256(combined.encode()).hexdigest()


# ── Core Engine ───────────────────────────────────────────────

class SpiderHashEngine:
    """
    Spider Hash Engine.

    Uses a HashStrategy to collect and mix hashes.
    Defaults to GenericStrategy if none provided.

    Usage with PlayWebit strategy:
        from supabase import create_client
        supabase = create_client(url, key)

        engine = SpiderHashEngine(
            strategy=PlayWebitStrategy(supabase)
        )
        result = engine.calculate(event_context={
            "nft_data":  nft_row,
            "timestamp": timestamp_ms
        })

    Usage with generic strategy:
        engine = SpiderHashEngine()
        result = engine.calculate(event_context={
            "table_hashes":  { "nfts": "abc...", "wallets": "def..." },
            "previous_hash": "000..."
        })
    """

    def __init__(self, strategy: Optional[HashStrategy] = None):
        """
        Args:
            strategy: HashStrategy instance. Defaults to GenericStrategy.
        """
        self.strategy = strategy or GenericStrategy()
        self.version  = "1.0.0"

    def calculate(self, event_context: Dict) -> Dict:
        """
        Calculate a Spider Hash using the configured strategy.

        Args:
            event_context: Dict passed directly to strategy.collect_hashes()

        Returns:
            {
                "spider_hash": str,       — final 64-char hash
                "components":  dict,      — individual component hashes
                "strategy":    str        — strategy class name
            }
        """
        components  = self.strategy.collect_hashes(event_context)
        spider_hash = self.strategy.mix_hashes(components)

        return {
            "spider_hash": spider_hash,
            "components":  components,
            "strategy":    self.strategy.__class__.__name__
        }

    def verify(
        self,
        stored_hash:   str,
        event_context: Dict
    ) -> bool:
        """
        Verify a stored Spider Hash matches current state.

        Args:
            stored_hash:   Hash stored on blockchain
            event_context: Same context used when hash was created

        Returns:
            True if valid, False if tampered
        """
        result = self.calculate(event_context)
        return result["spider_hash"] == stored_hash

    def hash_row(self, row_data: Dict) -> str:
        """Hash a single database row deterministically."""
        serialized = json.dumps(row_data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
