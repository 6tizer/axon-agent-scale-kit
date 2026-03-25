import json
from pathlib import Path
from web3 import Web3


def main() -> int:
    state = json.loads(Path("state/deploy_state.json").read_text())
    agent_names = [f"agent-{i:03d}" for i in range(1, 6)]
    w3 = Web3(
        Web3.HTTPProvider(
            "https://mainnet-rpc.axonchain.ai/",
            request_kwargs={"timeout": 20, "proxies": {"http": None, "https": None}},
        )
    )
    registry_abi = [
        {
            "inputs": [{"name": "account", "type": "address"}],
            "name": "isAgent",
            "outputs": [{"name": "", "type": "bool"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [{"name": "account", "type": "address"}],
            "name": "getAgent",
            "outputs": [
                {"name": "agentId", "type": "string"},
                {"name": "capabilities", "type": "string[]"},
                {"name": "model", "type": "string"},
                {"name": "reputation", "type": "uint64"},
                {"name": "isOnline", "type": "bool"},
            ],
            "stateMutability": "view",
            "type": "function",
        },
    ]
    reputation_abi = [
        {
            "inputs": [{"name": "agent", "type": "address"}],
            "name": "getReputation",
            "outputs": [{"name": "", "type": "uint64"}],
            "stateMutability": "view",
            "type": "function",
        }
    ]
    registry = w3.eth.contract(address=Web3.to_checksum_address("0x0000000000000000000000000000000000000801"), abi=registry_abi)
    reputation_contract = w3.eth.contract(address=Web3.to_checksum_address("0x0000000000000000000000000000000000000802"), abi=reputation_abi)

    items = []
    for name in agent_names:
        item = state.get("agents", {}).get(name, {})
        wallet_address = item.get("wallet_address")
        balance_axon = None
        registered_onchain = None
        reputation_onchain = None
        online_onchain = None
        error = ""
        if wallet_address:
            try:
                caddr = Web3.to_checksum_address(wallet_address)
                registered_onchain = bool(registry.functions.isAgent(caddr).call())
                balance_axon = w3.eth.get_balance(caddr) / 10**18
                if registered_onchain:
                    data = registry.functions.getAgent(caddr).call()
                    reputation_onchain = int(data[3])
                    online_onchain = bool(data[4])
                else:
                    reputation_onchain = int(reputation_contract.functions.getReputation(caddr).call())
            except Exception as exc:
                error = str(exc)
        items.append(
            {
                "agent": name,
                "wallet_address": wallet_address,
                "balance_axon": balance_axon,
                "registered_local": bool(item.get("registered")),
                "registered_onchain": registered_onchain,
                "reputation_onchain": reputation_onchain,
                "online_onchain": online_onchain,
                "last_heartbeat_block_onchain": None,
                "heartbeat_at_local": item.get("heartbeat_at"),
                "note": "last_heartbeat_block 需 Cosmos x/agent 数据；当前 EVM 接口不可直接返回",
                "error": error,
            }
        )
    print(json.dumps({"rpc_connected": w3.is_connected(), "latest_block": w3.eth.block_number, "items": items}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
