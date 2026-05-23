"""
adapters/playwebit_adapter.py
------------------------------
PlayWebit Blockchain Adapter — Spider Chain SDK

Connects Spider Chain to the PlayWebit Network (chain ID 4968).
This is the native blockchain of CipherVault.

Usage:
    from spiderchain.adapters.playwebit_adapter import PlayWebitAdapter

    adapter = PlayWebitAdapter(
        node_url="https://priyanshu23456-cipherv.hf.space"
    )
"""

import json
import time
import hashlib
from typing import Dict, Optional, List

from adapters.base_blockchain_adapter import BaseBlockchainAdapter


class PlayWebitAdapter(BaseBlockchainAdapter):
    """
    PlayWebit Network implementation of BaseBlockchainAdapter.

    Communicates with the PlayWebit node via its REST API
    to anchor and verify Spider Hashes on-chain.
    """

    def __init__(self, node_url: str, authority_wallet: Optional[str] = None):
        """
        Args:
            node_url:         URL of the PlayWebit node
                              e.g. "https://priyanshu23456-cipherv.hf.space"
            authority_wallet: Optional authority wallet address for signing
        """
        self.node_url = node_url.rstrip("/")
        self.authority_wallet = authority_wallet
        self.chain_id = 4968
        self.currency = "PLWB"

    def anchor_hash(
        self,
        spider_hash: str,
        chain_id: str,
        event_type: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Anchor a Spider Hash on PlayWebit via a transaction.

        Creates a zero-value transaction with the Spider Hash
        embedded in the transaction data field.
        """
        try:
            import requests

            payload = {
                "type": "spider_hash_anchor",
                "spider_hash": spider_hash,
                "chain_id": chain_id,
                "event_type": event_type,
                "metadata": metadata or {},
                "timestamp": int(time.time() * 1000)
            }

            response = requests.post(
                f"{self.node_url}/api/anchor_spider_hash",
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("tx_hash", self._generate_mock_tx_hash(spider_hash))

            raise RuntimeError(
                f"PlayWebit node returned {response.status_code}: {response.text}"
            )

        except ImportError:
            raise ImportError("requests package not installed. Run: pip install requests")

    def verify_on_chain(self, tx_hash: str) -> Dict:
        """Verify a Spider Hash transaction exists on PlayWebit."""
        try:
            import requests

            response = requests.get(
                f"{self.node_url}/api/transaction/{tx_hash}",
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "verified": True,
                    "spider_hash": data.get("spider_hash"),
                    "block_number": data.get("block_number"),
                    "timestamp": data.get("timestamp")
                }

            return {
                "verified": False,
                "spider_hash": None,
                "block_number": None,
                "timestamp": None
            }

        except Exception as e:
            return {"verified": False, "error": str(e)}

    def get_anchored_hashes(self, chain_id: str, limit: int = 50) -> List[Dict]:
        """Get all Spider Hashes anchored for a chain_id on PlayWebit."""
        try:
            import requests

            response = requests.get(
                f"{self.node_url}/api/spider_hashes/{chain_id}",
                params={"limit": limit},
                timeout=30
            )

            if response.status_code == 200:
                return response.json().get("hashes", [])

            return []

        except Exception:
            return []

    def _generate_mock_tx_hash(self, spider_hash: str) -> str:
        """Fallback tx hash if node doesn't return one."""
        data = f"{spider_hash}{time.time()}"
        return "0x" + hashlib.sha256(data.encode()).hexdigest()
