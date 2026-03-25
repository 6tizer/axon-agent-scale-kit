import json
from pathlib import Path
from web3 import Web3
from eth_account import Account


def to_wei(x: float) -> int:
    return int(x * 10**18)


def main() -> int:
    state_path = Path("state/deploy_state.json")
    state = json.loads(state_path.read_text())
    rpc = "https://mainnet-rpc.axonchain.ai/"
    chain_id = 8210
    funding_address = state.get("settings", {}).get("funding_address", "")
    if not funding_address:
        print(json.dumps({"ok": False, "error": "funding_address not set in state.settings"}, ensure_ascii=False, indent=2))
        return 1
    funding_wallet = None
    for w in state.get("wallets", {}).values():
        if str(w.get("address", "")).lower() == funding_address.lower():
            funding_wallet = w
            break
    if not funding_wallet:
        print(json.dumps({"ok": False, "error": "funding wallet private key not found in state.wallets"}, ensure_ascii=False, indent=2))
        return 1
    funding_pk = str(funding_wallet.get("private_key", ""))
    if not funding_pk:
        print(json.dumps({"ok": False, "error": "funding private key is empty"}, ensure_ascii=False, indent=2))
        return 1
    if not funding_pk.startswith("0x"):
        funding_pk = "0x" + funding_pk
    agent_names = [f"agent-{i:03d}" for i in range(1, 6)]
    agent_wallets = []
    Account.enable_unaudited_hdwallet_features()
    for name in agent_names:
        addr = state.get("agents", {}).get(name, {}).get("wallet_address")
        priv = ""
        key_id = ""
        for k, w in state.get("wallets", {}).items():
            if w.get("label") == f"agent:{name}" and w.get("role") == "agent":
                addr = w.get("address")
                priv = str(w.get("private_key", ""))
                key_id = k
                break
        if not addr:
            acct, mnemonic = Account.create_with_mnemonic()
            addr = acct.address
            priv = acct.key.hex()
            key_id = f"agent-{name[-3:]}"
            state.setdefault("wallets", {})[key_id] = {"address": addr, "private_key": priv, "role": "agent", "label": f"agent:{name}", "mnemonic": mnemonic}
        if not priv:
            for w in state.get("wallets", {}).values():
                if str(w.get("address", "")).lower() == str(addr).lower():
                    priv = str(w.get("private_key", ""))
                    break
        if not priv:
            acct, mnemonic = Account.create_with_mnemonic()
            addr = acct.address
            priv = acct.key.hex()
            if not key_id:
                key_id = f"agent-{name[-3:]}"
            state.setdefault("wallets", {})[key_id] = {"address": addr, "private_key": priv, "role": "agent", "label": f"agent:{name}", "mnemonic": mnemonic}
        state["agents"].setdefault(name, {})
        state["agents"][name]["wallet_address"] = addr
        if not priv.startswith("0x"):
            priv = "0x" + priv
        agent_wallets.append({"agent": name, "address": addr, "private_key": priv})
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30, "proxies": {"http": None, "https": None}}))
    if not w3.is_connected():
        print(json.dumps({"ok": False, "error": "rpc not connected"}, ensure_ascii=False, indent=2))
        return 1
    registry_abi = [
        {"inputs": [{"name": "account", "type": "address"}], "name": "isAgent", "outputs": [{"name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
        {"inputs": [{"name": "account", "type": "address"}], "name": "getAgent", "outputs": [{"name": "agentId", "type": "string"}, {"name": "capabilities", "type": "string[]"}, {"name": "model", "type": "string"}, {"name": "reputation", "type": "uint64"}, {"name": "isOnline", "type": "bool"}], "stateMutability": "view", "type": "function"},
        {"inputs": [{"name": "capabilities", "type": "string"}, {"name": "model", "type": "string"}], "name": "register", "outputs": [], "stateMutability": "payable", "type": "function"},
        {"inputs": [], "name": "heartbeat", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    ]
    reputation_abi = [{"inputs": [{"name": "agent", "type": "address"}], "name": "getReputation", "outputs": [{"name": "", "type": "uint64"}], "stateMutability": "view", "type": "function"}]
    registry = w3.eth.contract(address=Web3.to_checksum_address("0x0000000000000000000000000000000000000801"), abi=registry_abi)
    reputation = w3.eth.contract(address=Web3.to_checksum_address("0x0000000000000000000000000000000000000802"), abi=reputation_abi)
    funding_account = Account.from_key(funding_pk)
    target_fund = to_wei(110.0)
    stake_wei = to_wei(100.0)
    funding_nonce = w3.eth.get_transaction_count(funding_account.address)
    transfer_results = []
    register_results = []
    for aw in agent_wallets:
        caddr = Web3.to_checksum_address(aw["address"])
        already = bool(registry.functions.isAgent(caddr).call())
        bal = w3.eth.get_balance(caddr)
        tx_hash = ""
        if (not already) and bal < target_fund:
            amount = target_fund - bal
            tx = {
                "from": funding_account.address,
                "to": caddr,
                "value": amount,
                "nonce": funding_nonce,
                "gas": 21000,
                "gasPrice": w3.eth.gas_price,
                "chainId": chain_id,
            }
            signed = funding_account.sign_transaction(tx)
            sent = w3.eth.send_raw_transaction(signed.raw_transaction)
            rcpt = w3.eth.wait_for_transaction_receipt(sent, timeout=180)
            funding_nonce += 1
            tx_hash = sent.hex()
            if int(rcpt.status) != 1:
                print(json.dumps({"ok": False, "error": f"fund transfer failed for {aw['agent']}", "tx_hash": tx_hash}, ensure_ascii=False, indent=2))
                return 1
        transfer_results.append({"agent": aw["agent"], "address": aw["address"], "fund_tx_hash": tx_hash})
    for aw in agent_wallets:
        caddr = Web3.to_checksum_address(aw["address"])
        already = bool(registry.functions.isAgent(caddr).call())
        reg_tx_hash = ""
        if not already:
            acct = Account.from_key(aw["private_key"])
            nonce = w3.eth.get_transaction_count(acct.address)
            tx = registry.functions.register("validation,heartbeat,docker-managed", "axon-agent-scale-kit-v1").build_transaction(
                {
                    "from": acct.address,
                    "value": stake_wei,
                    "nonce": nonce,
                    "gas": 2_000_000,
                    "gasPrice": w3.eth.gas_price,
                    "chainId": chain_id,
                }
            )
            signed = acct.sign_transaction(tx)
            sent = w3.eth.send_raw_transaction(signed.raw_transaction)
            rcpt = w3.eth.wait_for_transaction_receipt(sent, timeout=180)
            reg_tx_hash = sent.hex()
            if int(rcpt.status) != 1:
                print(json.dumps({"ok": False, "error": f"register failed for {aw['agent']}", "tx_hash": reg_tx_hash}, ensure_ascii=False, indent=2))
                return 1
        now_agent = bool(registry.functions.isAgent(caddr).call())
        info = registry.functions.getAgent(caddr).call() if now_agent else ("", [], "", 0, False)
        rep = int(reputation.functions.getReputation(caddr).call())
        heartbeat_tx_hash = ""
        heartbeat_block = None
        if now_agent:
            acct = Account.from_key(aw["private_key"])
            nonce = w3.eth.get_transaction_count(acct.address)
            hb_tx = registry.functions.heartbeat().build_transaction(
                {
                    "from": acct.address,
                    "value": 0,
                    "nonce": nonce,
                    "gas": 300000,
                    "gasPrice": w3.eth.gas_price,
                    "chainId": chain_id,
                }
            )
            hb_signed = acct.sign_transaction(hb_tx)
            hb_sent = w3.eth.send_raw_transaction(hb_signed.raw_transaction)
            hb_receipt = w3.eth.wait_for_transaction_receipt(hb_sent, timeout=180)
            if int(hb_receipt.status) == 1:
                heartbeat_tx_hash = hb_sent.hex()
                heartbeat_block = int(hb_receipt.blockNumber)
        register_results.append(
            {
                "agent": aw["agent"],
                "address": aw["address"],
                "registered_onchain": now_agent,
                "reputation_onchain": rep,
                "online_onchain": bool(info[4]) if now_agent else None,
                "register_tx_hash": reg_tx_hash,
                "heartbeat_tx_hash": heartbeat_tx_hash,
                "last_heartbeat_block": heartbeat_block,
                "balance_after_axon": w3.eth.get_balance(caddr) / 10**18,
            }
        )
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {
                "ok": True,
                "latest_block": w3.eth.block_number,
                "funding_address": funding_account.address,
                "funding_balance_after_axon": w3.eth.get_balance(funding_account.address) / 10**18,
                "transfer_results": transfer_results,
                "register_results": register_results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
