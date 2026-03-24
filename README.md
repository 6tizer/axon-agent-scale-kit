# AXON Agent Scale Kit

Automation toolkit for AXON agent daily scaling workflows.

## Scope

- Validate network and agent configuration
- Create funded scale requests and funding gate checks
- Generate scale plans with budget and batch strategy
- Execute idempotent scaling, status reports and repair actions
- Generate, list, export and backup all wallet keys (funding + agent wallets)

## Wallet Management

All wallets (funding address + per-agent wallets) are generated locally with
real keys. Private keys and mnemonics are shown ONCE at generation time and
cannot be recovered. You MUST back them up immediately.

### Funding wallet (receives AXON transfers)
```bash
python scripts/axonctl.py wallet-generate --role funding --label "my-funding-wallet"
python scripts/axonctl.py wallet-list
```
Use the generated address as the destination for your AXON transfers.

To set an existing address as the funding wallet:
```bash
python scripts/axonctl.py funding-wallet-set --address 0x...
python scripts/axonctl.py funding-wallet-get
```

### Agent wallets (created automatically during scale)
```bash
python scripts/axonctl.py wallet-list
python scripts/axonctl.py wallet-export --key-id <key_id>
```
**Backup all agent wallets after each scale run.** Private keys are stored in
the state file but can be exported on demand.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 1. generate a funding wallet and use its address for transfers
python scripts/axonctl.py wallet-generate --role funding --label "my-funding"
# ^ copy the address from output and transfer AXON to it

# 2. validate configuration
python scripts/axonctl.py validate \
  --network configs/network.yaml \
  --agents configs/agents.yaml

# 3. trigger scaling with natural language
python scripts/axonctl.py run-intent \
  --network configs/network.yaml \
  --agents configs/agents.yaml \
  --intent "我打250 AXON，扩容2个Agents"

# 4. export and backup all agent wallet keys
python scripts/axonctl.py wallet-list
python scripts/axonctl.py wallet-export --key-id <key_id>
```

## Layout

- `configs/`: network and agent declaration files
- `scripts/`: CLI and execution scripts
- `templates/`: systemd templates
- `state/`: local state data (contains private keys — keep it safe)
- `tests/`: regression test suite
