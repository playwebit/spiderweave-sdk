"""
adapters/base_blockchain_adapter.py
------------------------------------
Base Blockchain Adapter — SpiderWeave SDK

Defines the interface every blockchain adapter must implement.
If you can write these 3 methods for your blockchain,
SpiderWeave anchors to it automatically.

Supported out of the box:
    - PlayWebit  (playwebit_adapter.py)
    - Ethereum / EVM chains  (evm_adapter.py)

To add your own blockchain, subclass BaseBlockchainAdapter
and implement the 3 methods below.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional


class BaseBlockchainAdapter(ABC):
    """
    Abstract interface for blockchain adapters.

    SpiderWeave calls these 3 methods to anchor and verify
    Spider Hashes on-chain. Implement them for your blockchain.
    """

    @abstractmethod
    def anchor_hash(
        self,
        spider_hash: str,
        chain_id: str,
        event_type: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Write a Spider Hash onto the blockchain.

        This is the on-chain anchoring step. The Spider Hash
        becomes immutable proof of the database state at this moment.

        Args:
            spider_hash: The 64-char Spider Hash to anchor
            chain_id:    Identifier for this chain (token_id, user_id, etc.)
            event_type:  Human-readable event label ("mint", "transfer", etc.)
            metadata:    Optional extra data to include in the transaction

        Returns:
            Transaction hash (proof of anchoring)
        """
        pass

    @abstractmethod
    def verify_on_chain(self, tx_hash: str) -> Dict:
        """
        Verify a Spider Hash exists on-chain.

        Args:
            tx_hash: Transaction hash returned by anchor_hash()

        Returns:
            {
                "verified": bool,
                "spider_hash": str,
                "block_number": int,
                "timestamp": int
            }
        """
        pass

    @abstractmethod
    def get_anchored_hashes(self, chain_id: str, limit: int = 50) -> list:
        """
        Get all Spider Hashes anchored on-chain for a given chain_id.

        Args:
            chain_id: Chain identifier
            limit:    Max results to return

        Returns:
            List of { tx_hash, spider_hash, event_type, timestamp, block_number }
        """
        pass
