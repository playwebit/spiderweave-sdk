"""
adapters/evm_adapter.py
------------------------
EVM Blockchain Adapter — Spider Chain SDK

Works with any EVM-compatible blockchain:
    - Ethereum mainnet / testnets
    - Polygon
    - BNB Chain
    - Avalanche
    - Any chain with an RPC endpoint

Install dependency:
    pip install web3

Usage:
    from spiderchain.adapters.evm_adapter import EVMAdapter

    # Ethereum
    adapter = EVMAdapter(
        rpc_url="https://mainnet.infura.io/v3/YOUR_KEY",
        private_key="0x..."  # Optional, for signing transactions
    )

    # Polygon
    adapter = EVMAdapter(rpc_url="https://polygon-rpc.com")
"""

import json
import time
import hashlib
from typing import Dict, Optional, List

from adapters.base_blockchain_adapter import BaseBlockchainAdapter


class EVMAdapter(BaseBlockchainAdapter):
    """
    EVM-compatible blockchain implementation of BaseBlockchainAdapter.

    Anchors Spider Hashes by writing them as transaction input data
    on any EVM-compatible chain. Uses web3.py under the hood.
    """

    def __init__(
        self,
        rpc_url: str,
        private_key: Optional[str] = None,
        contract_address: Optional[str] = None
    ):
        """
        Args:
            rpc_url:          RPC endpoint for your EVM chain
            private_key:      Private key for signing transactions (optional)
                              If not provided, operates in read-only mode
            contract_address: Optional Spider Chain smart contract address
                              for structured on-chain storage
        """
        try:
            from web3 import Web3
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        except ImportError:
            raise ImportError(
                "web3 package not installed. Run: pip install web3"
            )

        self.rpc_url = rpc_url
        self.private_key = private_key
        self.contract_address = contract_address

        if not self.w3.is_connected():
            raise ConnectionError(f"Could not connect to EVM node at {rpc_url}")

    def anchor_hash(
        self,
        spider_hash: str,
        chain_id: str,
        event_type: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Anchor a Spider Hash on an EVM chain.

        Encodes the Spider Hash as transaction input data.
        This creates an immutable on-chain record of the hash.

        If no private key is provided, returns a simulated tx hash
        (useful for testing).
        """
        if not self.private_key:
            return self._simulate_tx_hash(spider_hash)

        from web3 import Web3

        payload = {
            "type": "spider_hash",
            "hash": spider_hash,
            "chain_id": chain_id,
            "event": event_type,
            "ts": int(time.time() * 1000)
        }

        account = self.w3.eth.account.from_key(self.private_key)
        data = "0x" + json.dumps(payload).encode().hex()

        tx = {
            "from": account.address,
            "to": self.contract_address or account.address,
            "value": 0,
            "data": data,
            "gas": 100000,
            "gasPrice": self.w3.eth.gas_price,
            "nonce": self.w3.eth.get_transaction_count(account.address),
            "chainId": self.w3.eth.chain_id
        }

        signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        return tx_hash.hex()

    def verify_on_chain(self, tx_hash: str) -> Dict:
        """Verify a Spider Hash transaction exists on the EVM chain."""
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            tx = self.w3.eth.get_transaction(tx_hash)
            block = self.w3.eth.get_block(receipt.blockNumber)

            return {
                "verified": receipt.status == 1,
                "spider_hash": self._extract_hash_from_tx(tx),
                "block_number": receipt.blockNumber,
                "timestamp": block.timestamp
            }

        except Exception as e:
            return {"verified": False, "error": str(e)}

    def get_anchored_hashes(self, chain_id: str, limit: int = 50) -> List[Dict]:
        """
        Get anchored Spider Hashes from the EVM chain.

        Note: For full history queries, you need an indexed node
        or a subgraph. This method returns an empty list if no
        contract address is set.
        """
        if not self.contract_address:
            return []

        return []

    def _extract_hash_from_tx(self, tx) -> Optional[str]:
        """Try to extract Spider Hash from transaction input data."""
        try:
            data = bytes.fromhex(tx.input[2:]).decode("utf-8")
            payload = json.loads(data)
            return payload.get("hash")
        except Exception:
            return None

    def _simulate_tx_hash(self, spider_hash: str) -> str:
        """Generate a deterministic mock tx hash for testing."""
        data = f"{spider_hash}{time.time()}"
        return "0x" + hashlib.sha256(data.encode()).hexdigest()
