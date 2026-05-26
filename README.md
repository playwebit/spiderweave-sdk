# SpiderWeave SDK

**Cross-table hash architecture for tamper-proof blockchain data integrity.**

SpiderWeave links your database tables together with cryptographic hashes and anchors the result on any blockchain. If anyone tampers with even a single row in any table — the entire chain breaks instantly, exposing the attack.

Invented by **Priyanshu Chauhan / PlayWebit** as part of the SpiderWeave Hash Architecture research.

---

## The Problem It Solves

NFT metadata and transaction data are typically stored off-chain (in a database like Supabase or PostgreSQL). This creates a vulnerability: anyone with database access can silently change a record — altering ownership, price, or metadata — without the blockchain knowing.

**SpiderWeave fixes this** by creating a cryptographic fingerprint that spans multiple tables simultaneously. Change anything, anywhere — and the fingerprint breaks.

---

## How It Works

```
Table: nfts       → hash_1 ──┐
Table: wallets    → hash_2 ──┤
Table: sessions   → hash_3 ──┼──► Spider Hash ──► Blockchain
Table: marketplace→ hash_4 ──┤         ▲
Table: contracts  → hash_5 ──┘         │
                                  Previous hash
                                  (chain link)
```

Every event (mint, transfer, sale) produces a new Spider Hash that:
1. Includes a hash from every registered table row
2. Links to the previous Spider Hash (forming a chain)
3. Gets anchored permanently on your blockchain

If someone changes `wallets.balance` after a mint — the Spider Hash from that mint no longer matches. Tamper detected.

---

## Installation

```bash
pip install spiderweave
```

Install with your database driver:

```bash
pip install spiderweave[supabase]    # Supabase
pip install spiderweave[postgres]    # PostgreSQL / MySQL
pip install spiderweave[evm]         # Ethereum / Polygon / EVM chains
pip install spiderweave[all]         # Everything
```

---

## Quick Start

### With Supabase + PlayWebit

```python
from spiderweave import SpiderWeave
from spiderweave.adapters.supabase_adapter import SupabaseAdapter
from spiderweave.adapters.playwebit_adapter import PlayWebitAdapter

# Connect your database and blockchain
sc = SpiderWeave(
    db_adapter=SupabaseAdapter(
        url="https://your-project.supabase.co",
        key="your-anon-key"
    ),
    blockchain_adapter=PlayWebitAdapter(
        node_url="https://your-playwebit-node.hf.space"
    )
)

# Tell SpiderWeave which tables to watch
sc.register_table("nfts",        lookup_key="token_id")
sc.register_table("wallets",     lookup_key="user_id")
sc.register_table("sessions",    lookup_key="user_id")
sc.register_table("marketplace", lookup_key="token_id")

# When a user mints an NFT — create and anchor the Spider Hash
result = sc.create_and_anchor(
    chain_id="token_abc123",
    event_type="mint",
    event_context={
        "token_id": "abc123",
        "user_id": "0xabc..."
    }
)

print(result["spider_hash"])  # 64-char hash stored on blockchain
print(result["tx_hash"])      # blockchain transaction proof
```

### With PostgreSQL + Ethereum

```python
from spiderweave import SpiderWeave
from spiderweave.adapters.postgres_adapter import PostgresAdapter
from spiderweave.adapters.evm_adapter import EVMAdapter

sc = SpiderWeave(
    db_adapter=PostgresAdapter(
        connection_string="postgresql://user:pass@localhost:5432/mydb"
    ),
    blockchain_adapter=EVMAdapter(
        rpc_url="https://mainnet.infura.io/v3/YOUR_KEY",
        private_key="0x..."
    )
)

sc.register_table("users",    lookup_key="user_id")
sc.register_table("orders",   lookup_key="order_id", is_anchor=True)
sc.register_table("payments", lookup_key="order_id")

result = sc.create_and_anchor(
    chain_id="order_99",
    event_type="payment_confirmed",
    event_context={"order_id": "99", "user_id": "42"}
)
```

### Hash Only (No Blockchain)

```python
sc = SpiderWeave(db_adapter=SupabaseAdapter(url="...", key="..."))

sc.register_table("documents", lookup_key="doc_id")
sc.register_table("authors",   lookup_key="user_id")

hash_result = sc.create_spider_hash(
    chain_id="doc_001",
    event_context={"doc_id": "001", "user_id": "author_1"}
)

print(hash_result["spider_hash"])
print(hash_result["table_hashes"])  # hash from each individual table
```

---

## Verifying Integrity

```python
# Later — verify nothing has changed
result = sc.verify(
    chain_id="token_abc123",
    event_context={"token_id": "abc123", "user_id": "0xabc..."},
    stored_hash="the-spider-hash-from-your-blockchain",
    stored_timestamp=1716000000000
)

if result["valid"]:
    print("Data integrity confirmed")
else:
    print("TAMPER DETECTED")
    print(result["table_hashes"])  # see which tables changed
```

---

## Detecting Tampering

```python
from spiderweave.exceptions import TamperDetectedError

try:
    sc.detect_tamper(chain_id="token_abc123")
    print("Chain is clean")
except TamperDetectedError as e:
    print(f"Tamper detected at event {e.broken_at}")
    print(f"Compromised hash: {e.broken_hash}")
```

---

## View Chain History

```python
history = sc.get_chain_history("token_abc123")

for event in history:
    print(event["event_type"], event["spider_hash"][:16], event["timestamp"])

# mint         a3f9c2b1...  1716000000000
# list_sale    b7d4e8f2...  1716001000000
# transfer     c9a1f3d5...  1716002000000
```

---

## Writing a Custom Database Adapter

If you use MongoDB, Firebase, DynamoDB, or any other database — write a custom adapter in 5 methods:

```python
from spiderweave.adapters.base_adapter import BaseDBAdapter
import hashlib, json

class MongoDBAdapter(BaseDBAdapter):

    def __init__(self, connection_string, database_name):
        from pymongo import MongoClient
        self.db = MongoClient(connection_string)[database_name]

    def get_row_hash(self, table, row_id):
        row = self.db[table].find_one({"_id": row_id})
        if not row:
            return "0" * 64
        row.pop("_id", None)
        return hashlib.sha256(
            json.dumps(row, sort_keys=True, default=str).encode()
        ).hexdigest()

    def get_table_chain(self, table, row_id):
        return list(
            self.db["spider_chain_events"]
            .find({"table_name": table, "row_id": row_id})
            .sort("timestamp", 1)
        )

    def get_chain_history(self, chain_id, before_timestamp=None, limit=50):
        query = {"chain_id": chain_id}
        if before_timestamp:
            query["timestamp"] = {"$lt": before_timestamp}
        return list(
            self.db["spider_chain_events"]
            .find(query)
            .sort("timestamp", -1)
            .limit(limit)
        )

    def save_chain_event(self, event):
        self.db["spider_chain_events"].insert_one(event)

    def get_rows_for_event(self, table_config, event_context):
        rows = {}
        for table_def in table_config:
            name = table_def["name"]
            key = table_def.get("lookup_key", "_id")
            val = event_context.get(key)
            row = self.db[name].find_one({key: val}) or {}
            row.pop("_id", None)
            rows[name] = row
        return rows
```

Then use it exactly like the built-in adapters:

```python
sc = SpiderWeave(
    db_adapter=MongoDBAdapter("mongodb://localhost", "mydb"),
    blockchain_adapter=EVMAdapter(rpc_url="...")
)
```

---

## Writing a Custom Blockchain Adapter

For any blockchain not supported out of the box:

```python
from spiderweave.adapters.base_blockchain_adapter import BaseBlockchainAdapter

class SolanaAdapter(BaseBlockchainAdapter):

    def __init__(self, rpc_url, keypair_path):
        self.rpc_url = rpc_url
        self.keypair_path = keypair_path

    def anchor_hash(self, spider_hash, chain_id, event_type, metadata=None):
        # Write spider_hash to Solana via memo instruction
        # Return the transaction signature
        tx_sig = self._submit_memo(spider_hash)
        return tx_sig

    def verify_on_chain(self, tx_hash):
        # Look up the transaction on Solana
        tx = self._get_transaction(tx_hash)
        return {
            "verified": tx is not None,
            "spider_hash": self._extract_hash(tx),
            "block_number": tx.get("slot"),
            "timestamp": tx.get("blockTime")
        }

    def get_anchored_hashes(self, chain_id, limit=50):
        return []
```

---

## Required Database Table

SpiderWeave needs one table in your database to store chain events:

```sql
CREATE TABLE spider_chain_events (
    id          SERIAL PRIMARY KEY,
    chain_id    VARCHAR(255) NOT NULL,
    spider_hash VARCHAR(64)  NOT NULL,
    event_type  VARCHAR(100) NOT NULL,
    timestamp   BIGINT       NOT NULL,
    metadata    JSONB,
    previous_hash VARCHAR(64)
);

CREATE INDEX idx_spider_chain_chain_id ON spider_chain_events(chain_id);
CREATE INDEX idx_spider_chain_timestamp ON spider_chain_events(timestamp);
```

For Supabase, run this SQL in your project's SQL editor.

---

## API Reference

### `SpiderWeave(db_adapter, blockchain_adapter=None)`
Main SDK class. Create one instance per application.

### `.register_table(table_name, lookup_key="id", is_anchor=False)`
Register a table to participate in Spider Hash calculation. Returns `self` for chaining.

### `.create_and_anchor(chain_id, event_type, event_context, metadata=None)`
Calculate Spider Hash and anchor it on-chain. Returns full result dict.

### `.create_spider_hash(chain_id, event_context, timestamp=None)`
Calculate Spider Hash without anchoring. Returns hash result dict.

### `.anchor(spider_hash, chain_id, event_type, metadata=None)`
Anchor an existing Spider Hash on-chain.

### `.verify(chain_id, event_context, stored_hash, stored_timestamp)`
Verify current database state matches a stored Spider Hash.

### `.detect_tamper(chain_id)`
Walk chain history and detect broken links. Raises `TamperDetectedError` if found.

### `.get_chain_history(chain_id, limit=50)`
Return the event history for a chain.

---

## Exceptions

| Exception | When raised |
|---|---|
| `TamperDetectedError` | Chain integrity check fails |
| `ChainBrokenError` | Chain sequence is broken |
| `AdapterNotConfiguredError` | Missing db or blockchain adapter |
| `InvalidHashError` | Malformed hash value |
| `TableNotRegisteredError` | Using an unregistered table |

---

## Research & Citation

SpiderWeave Hash Architecture is an original invention described in:

> *SpiderWeave Hash Architecture: Cross-Table Tamper Detection for Off-Chain Blockchain Data*
> Priyanshu Chauhan / PlayWebit Research, 2026

If you use SpiderWeave SDK in academic work, please cite the above paper.

---

## License

MIT License. See LICENSE file for details.

---

## Contributing

SpiderWeave is open to community adapters for new databases and blockchains.
To contribute an adapter, implement `BaseDBAdapter` or `BaseBlockchainAdapter`
and open a pull request.
