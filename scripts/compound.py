"""
compound.py — Axon Agent Auto-Compounding Daemon

收益机制背景（基于 axon-chain/axon x/agent/keeper/ 源码精确分析）
─────────────────────────────────────────────────────────────────
收益流                  参与者            质押影响
──────────────────────────────────────────────────────────────────
区块奖励 Validator Pool  只有 active bonded  MiningPower = stake^0.5 × repScore
(55%)                  validator agents     质押翻4× → 矿力 ×2.0
区块奖励 Reputation Pool 所有非 suspended    仅按声誉权重，质押无影响
(25%)                  agents
贡献奖励 Contribution    rep≥20 且           质押决定每 agent 的奖励上限 cap
(35% of 1B)            注册≥7天             cap = pool×capBps×stake/10000/totalStake
旧版 Epoch Rewards       ONLINE agents       weight = stake × (100+repBonus+aiBonus)
                                            质押与 weight 线性正相关

复投优先级
──────────────────────────────────────────────────────────────────
1. qqclaw-validator: 激进复投
   - stake^0.5 贡献 Validator Pool 份额（边际递减但有效）
   - stake 线性提升贡献奖励 cap（linear）
   - stake 线性提升旧版 epoch rewards weight（linear）
2. 普通 agents (agent-001 ~ agent-009): 温和复投
   - 质押不影响 Reputation Pool（最主要来源）
   - 只对贡献奖励 cap 和旧版 rewards 有线性提升
   - 建议: 先确保声誉增长，多余资金再复投
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
import time

# ── 路径处理（与 axonctl.py 保持一致）──────────────────────────────────────
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import yaml

logger = logging.getLogger("compound")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"))
    logger.addHandler(_h)
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# ── 常量 ──────────────────────────────────────────────────────────────────
REGISTRY_PRECOMPILE = "0x0000000000000000000000000000000000000801"
ONE_AXON = 10 ** 18

COMPOUND_ABI = [
    {
        "inputs": [],
        "name": "addStake",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "getStakeInfo",
        "outputs": [
            {"name": "totalStake", "type": "uint256"},
            {"name": "pendingReduce", "type": "uint256"},
            {"name": "reduceUnlockHeight", "type": "uint64"},
        ],
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

# ── 默认配置 ──────────────────────────────────────────────────────────────
DEFAULT_COMPOUND_CFG = {
    # 复投触发阈值：free balance（扣除 reserve 后）超过此值才执行复投（单位 AXON）
    "min_compound_axon": 5.0,
    # 每个 agent 保留的最小 free 余额（gas 费用缓冲，单位 AXON）
    "reserve_axon": 1.0,
    # 最大 gas 价格（gwei）
    "max_gas_gwei": 30,
    # 等待 receipt 超时（秒）
    "receipt_timeout_sec": 120,
    # daemon 运行间隔（秒）默认 2 小时
    "interval_sec": 7200,
    # 每次 compound 最多复投的 AXON 数量（防止单次大额 TX）
    "max_compound_per_run_axon": 500.0,
    # 是否使用 dry_run（只计算，不发 TX）
    "dry_run": False,
}


# ── 工具函数 ──────────────────────────────────────────────────────────────

def _axon_to_wei(amount_axon: float) -> int:
    return int(float(amount_axon) * ONE_AXON)


def _wei_to_axon(amount_wei: int) -> float:
    return amount_wei / ONE_AXON


def load_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)


def _state_wallet_for_agent(state: dict, agent_name: str) -> dict | None:
    """从 deploy_state.json 中提取 agent 的钱包信息（与 axonctl.py 完全一致）"""
    wallets = state.get("wallets", {})

    # Primary: label format is "agent:{name}" (matches axonctl.py L1847)
    for key_id, info in wallets.items():
        if not isinstance(info, dict):
            continue
        if info.get("role") == "agent" and info.get("label") == f"agent:{agent_name}":
            return {"key_id": key_id, **info}

    # Fallback: look up wallet_address in state["agents"] then match by address
    # (mirrors axonctl.py L502-507)
    address = state.get("agents", {}).get(agent_name, {}).get("wallet_address", "")
    if not address:
        return None
    for key_id, info in wallets.items():
        if not isinstance(info, dict):
            continue
        if info.get("address", "").lower() == address.lower():
            return {"key_id": key_id, **info}

    return None


# ── 矿力计算器（镜像 mining_power.go CalcMiningPower）──────────────────────

def calc_mining_power(stake_axon: float, reputation: int, alpha: float = 0.5, beta: float = 1.5, r_max: int = 100) -> float:
    """
    计算单个 agent 的矿力值（浮点近似，用于策略决策）。

    公式（来自 x/agent/keeper/mining_power.go）：
      StakeScore      = stake ^ alpha          (alpha = 0.5 → √stake)
      ReputationScore = 1 + beta × ln(1 + rep) / ln(rMax + 1)
      MiningPower     = StakeScore × ReputationScore
    """
    if stake_axon <= 0:
        return 0.0
    rep = max(0, min(reputation, r_max))
    stake_score = stake_axon ** alpha
    if rep <= 0:
        rep_score = 1.0
    else:
        rep_score = 1.0 + beta * math.log(1 + rep) / math.log(r_max + 1)
    return stake_score * rep_score


def calc_marginal_mining_power_gain(current_stake: float, add_stake: float, reputation: int) -> tuple[float, float]:
    """返回 (当前矿力, 复投后矿力)"""
    mp_before = calc_mining_power(current_stake, reputation)
    mp_after = calc_mining_power(current_stake + add_stake, reputation)
    return mp_before, mp_after


def calc_compound_roi(
    current_stake: float,
    add_stake: float,
    reputation: int,
    is_validator: bool,
    contribution_cap_bps: int = 200,
) -> dict:
    """
    计算复投 add_stake AXON 的理论收益提升倍率。

    Returns:
        {
          "mining_power_gain_pct":  float,  # Validator Pool 矿力提升 %（仅 validator）
          "contribution_cap_gain_pct": float, # 贡献奖励 cap 提升 %（与 stake 线性）
          "legacy_weight_gain_pct": float,   # 旧版 rewards weight 提升 %（与 stake 线性）
          "recommended": bool,               # 是否推荐复投
          "reason": str,
        }
    """
    if add_stake <= 0 or current_stake <= 0:
        return {"mining_power_gain_pct": 0.0, "contribution_cap_gain_pct": 0.0,
                "legacy_weight_gain_pct": 0.0, "recommended": False, "reason": "stake not positive"}

    new_stake = current_stake + add_stake

    # Validator Pool：MiningPower = stake^0.5 × repScore（只有 validator 享有）
    mp_before, mp_after = calc_marginal_mining_power_gain(current_stake, add_stake, reputation)
    mp_gain = (mp_after - mp_before) / mp_before * 100 if mp_before > 0 else 0.0

    # Contribution rewards cap：线性正比于 stake
    contrib_gain = (new_stake - current_stake) / current_stake * 100

    # 旧版 epoch rewards weight = stake × multiplier，与 stake 线性
    legacy_gain = contrib_gain  # 完全线性

    if is_validator:
        # Percentage thresholds OR absolute minimum: if compound_amount >= 10 AXON the
        # gas cost (~0.0003 AXON) is negligible compared to recurring epoch gains.
        recommended = mp_gain > 0.5 or contrib_gain > 1.0 or add_stake >= 10.0
        reason = (
            f"validator: mining power +{mp_gain:.1f}%, contribution cap +{contrib_gain:.1f}%"
            if recommended
            else "gain too marginal for gas cost"
        )
    else:
        # Non-validator: rep pool unaffected by stake; only contribution cap + legacy rewards benefit.
        # Same absolute floor: if >= 10 AXON, compound is worthwhile.
        recommended = contrib_gain > 1.0 or add_stake >= 10.0
        reason = (
            f"agent: contribution cap +{contrib_gain:.1f}%, legacy rewards +{legacy_gain:.1f}%"
            if recommended
            else "gain too marginal for gas cost (rep pool unaffected by stake)"
        )

    return {
        "mining_power_gain_pct": round(mp_gain, 2) if is_validator else 0.0,
        "contribution_cap_gain_pct": round(contrib_gain, 2),
        "legacy_weight_gain_pct": round(legacy_gain, 2),
        "recommended": recommended,
        "reason": reason,
    }


# ── 链上查询 ──────────────────────────────────────────────────────────────

def get_agent_onchain_info(rpc_url: str, chain_id: int, evm_address: str) -> dict:
    """
    查询 agent 的链上信息：余额、质押、声誉、在线状态。

    Returns dict with keys:
        balance_axon, stake_axon, pending_reduce_axon, reduce_unlock_height,
        reputation, is_online, is_registered, error
    """
    result: dict = {
        "address": evm_address,
        "balance_axon": 0.0,
        "stake_axon": 0.0,
        "pending_reduce_axon": 0.0,
        "reduce_unlock_height": 0,
        "reputation": 0,
        "is_online": False,
        "is_registered": False,
        "error": None,
    }
    try:
        from web3 import Web3
    except ImportError:
        result["error"] = "web3 not installed"
        return result

    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 20, "proxies": {"http": None, "https": None}}))
        if not w3.is_connected():
            result["error"] = "rpc not connected"
            return result

        checksum_addr = Web3.to_checksum_address(evm_address)
        balance_wei = w3.eth.get_balance(checksum_addr)
        result["balance_axon"] = _wei_to_axon(balance_wei)

        contract = w3.eth.contract(
            address=Web3.to_checksum_address(REGISTRY_PRECOMPILE),
            abi=COMPOUND_ABI,
        )

        try:
            stake_info = contract.functions.getStakeInfo(checksum_addr).call()
            # Returns (totalStake uint256, pendingReduce uint256, reduceUnlockHeight uint64)
            result["stake_axon"] = _wei_to_axon(stake_info[0])
            result["pending_reduce_axon"] = _wei_to_axon(stake_info[1])
            result["reduce_unlock_height"] = int(stake_info[2])
        except Exception as e:
            logger.warning("getStakeInfo failed for %s (stake_axon=0, ROI will skip): %s", evm_address, e)

        try:
            agent_info = contract.functions.getAgent(checksum_addr).call()
            # Returns (agentId string, capabilities string[], model string, reputation uint64, isOnline bool)
            result["reputation"] = int(agent_info[3])
            result["is_online"] = bool(agent_info[4])
            result["is_registered"] = bool(agent_info[0])  # agentId != ""
        except Exception as e:
            logger.debug("getAgent failed for %s: %s", evm_address, e)

    except Exception as e:
        result["error"] = str(e)

    return result


def submit_add_stake_tx(
    rpc_url: str,
    chain_id: int,
    private_key: str,
    amount_axon: float,
    max_gas_gwei: float = 30,
    receipt_timeout_sec: int = 120,
    dry_run: bool = False,
) -> dict:
    """
    向链上提交 addStake() 交易，将 amount_axon AXON 追加到 agent 质押。

    Returns dict with keys: ok, tx_hash, error, dry_run
    """
    if dry_run:
        return {"ok": True, "dry_run": True, "amount_axon": amount_axon,
                "tx_hash": "0x(dry_run)", "error": None}

    try:
        from eth_account import Account
        from web3 import Web3
    except ImportError:
        return {"ok": False, "error": "web3/eth_account not installed", "dry_run": False}

    pk = private_key if private_key.startswith("0x") else f"0x{private_key}"
    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 20, "proxies": {"http": None, "https": None}}))
        if not w3.is_connected():
            return {"ok": False, "error": "rpc not connected", "dry_run": False}

        acct = Account.from_key(pk)
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(REGISTRY_PRECOMPILE),
            abi=COMPOUND_ABI,
        )
        amount_wei = _axon_to_wei(amount_axon)
        nonce = w3.eth.get_transaction_count(acct.address, "pending")
        gas_price = min(w3.eth.gas_price, int(max_gas_gwei * 1e9))

        try:
            estimate = contract.functions.addStake().estimate_gas(
                {"from": acct.address, "value": amount_wei}
            )
            gas_limit = max(int(estimate * 1.2), 120_000)
        except Exception:
            gas_limit = 300_000

        tx = contract.functions.addStake().build_transaction(
            {
                "from": acct.address,
                "nonce": nonce,
                "gas": gas_limit,
                "gasPrice": gas_price,
                "chainId": chain_id,
                "value": amount_wei,
            }
        )
        signed = acct.sign_transaction(tx)
        tx_hash_bytes = w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hash = tx_hash_bytes.hex()
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=receipt_timeout_sec)

        if int(receipt.status) != 1:
            return {"ok": False, "error": "tx receipt status != 1", "tx_hash": tx_hash, "dry_run": False}

        return {
            "ok": True,
            "tx_hash": tx_hash,
            "amount_axon": amount_axon,
            "block_number": int(receipt.blockNumber),
            "error": None,
            "dry_run": False,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "dry_run": False}


# ── 复投计划 ──────────────────────────────────────────────────────────────

def build_compound_plan(
    state: dict,
    agents_cfg: dict,
    network_cfg: dict,
    compound_cfg: dict,
) -> list[dict]:
    """
    扫描所有 agents，返回复投计划列表。

    每个计划项包含：
      agent_name, evm_address, is_validator, balance_axon, stake_axon,
      reputation, compound_amount_axon, roi_info, action (compound/skip/no_wallet)
    """
    rpc_url = network_cfg.get("rpc_url", "")
    chain_id = int(network_cfg.get("evm_chain_id", 8210))
    min_compound = float(compound_cfg.get("min_compound_axon", DEFAULT_COMPOUND_CFG["min_compound_axon"]))
    reserve = float(compound_cfg.get("reserve_axon", DEFAULT_COMPOUND_CFG["reserve_axon"]))
    max_per_run = float(compound_cfg.get("max_compound_per_run_axon", DEFAULT_COMPOUND_CFG["max_compound_per_run_axon"]))

    plans = []

    for agent_item in agents_cfg.get("agents", []):
        name = agent_item.get("name", "")
        is_validator = bool(agent_item.get("is_validator", False))

        wallet = _state_wallet_for_agent(state, name)
        if not wallet:
            plans.append({
                "agent_name": name,
                "is_validator": is_validator,
                "action": "no_wallet",
                "reason": "wallet not found in state",
            })
            continue

        evm_address = wallet.get("address", "")
        if not evm_address:
            plans.append({
                "agent_name": name,
                "is_validator": is_validator,
                "action": "no_wallet",
                "reason": "address missing in state",
            })
            continue

        info = get_agent_onchain_info(rpc_url, chain_id, evm_address)
        if info.get("error"):
            plans.append({
                "agent_name": name,
                "evm_address": evm_address,
                "is_validator": is_validator,
                "action": "error",
                "reason": info["error"],
            })
            continue

        if not info.get("is_registered"):
            plans.append({
                "agent_name": name,
                "evm_address": evm_address,
                "is_validator": is_validator,
                "action": "skip",
                "reason": "agent not registered on-chain",
                "balance_axon": info["balance_axon"],
            })
            continue

        if not info.get("is_online"):
            plans.append({
                "agent_name": name,
                "evm_address": evm_address,
                "is_validator": is_validator,
                "action": "skip",
                "reason": "agent offline — fix connectivity first",
                "balance_axon": info["balance_axon"],
                "stake_axon": info["stake_axon"],
                "reputation": info["reputation"],
            })
            continue

        free_balance = info["balance_axon"] - reserve
        if free_balance < min_compound:
            plans.append({
                "agent_name": name,
                "evm_address": evm_address,
                "is_validator": is_validator,
                "action": "skip",
                "reason": f"free balance {free_balance:.4f} AXON < min {min_compound} AXON",
                "balance_axon": info["balance_axon"],
                "stake_axon": info["stake_axon"],
                "reputation": info["reputation"],
            })
            continue

        compound_amount = min(free_balance, max_per_run)

        roi = calc_compound_roi(
            current_stake=info["stake_axon"],
            add_stake=compound_amount,
            reputation=info["reputation"],
            is_validator=is_validator,
        )

        plans.append({
            "agent_name": name,
            "evm_address": evm_address,
            "is_validator": is_validator,
            "action": "compound" if roi["recommended"] else "skip",
            "reason": roi["reason"],
            "balance_axon": info["balance_axon"],
            "stake_axon": info["stake_axon"],
            "pending_reduce_axon": info["pending_reduce_axon"],
            "reputation": info["reputation"],
            "compound_amount_axon": compound_amount,
            "roi_info": roi,
        })

    return plans


# ── 复投执行 ──────────────────────────────────────────────────────────────

def compound_run_once(
    state_file: str,
    network: str,
    agents: str,
    compound_cfg: dict | None = None,
    dry_run: bool = False,
) -> int:
    """
    执行一次完整的复投循环，对所有 agents 进行计划 + 执行。

    Returns: 0 = success, 1 = partial failure, 2 = fatal error
    """
    state = load_state(state_file)
    network_cfg = load_yaml(network)
    agents_cfg = load_yaml(agents)
    cfg = {**DEFAULT_COMPOUND_CFG, **(compound_cfg or {})}
    if dry_run:
        cfg["dry_run"] = True

    rpc_url = network_cfg.get("rpc_url", "")
    chain_id = int(network_cfg.get("evm_chain_id", 8210))
    max_gas_gwei = float(network_cfg.get("gas", {}).get("max_gwei", 30))
    receipt_timeout = int(cfg.get("receipt_timeout_sec", 120))

    logger.info("=== compound run start (dry_run=%s) ===", cfg["dry_run"])

    plans = build_compound_plan(state, agents_cfg, network_cfg, cfg)

    results = []
    had_error = False

    for plan in plans:
        name = plan["agent_name"]
        action = plan.get("action", "skip")

        if action != "compound":
            logger.info("[%s] %s → %s", name, action, plan.get("reason", ""))
            results.append({"agent": name, "action": action, "reason": plan.get("reason", "")})
            continue

        amount = plan["compound_amount_axon"]
        logger.info(
            "[%s] compounding %.4f AXON (stake: %.2f → %.2f, rep: %d, validator: %s)",
            name, amount,
            plan.get("stake_axon", 0),
            plan.get("stake_axon", 0) + amount,
            plan.get("reputation", 0),
            plan["is_validator"],
        )

        wallet = _state_wallet_for_agent(state, name)
        private_key = wallet.get("private_key") or ""
        if not private_key:
            logger.warning("[%s] private key not found in state", name)
            results.append({"agent": name, "action": "error", "reason": "private key missing"})
            had_error = True
            continue

        tx_result = submit_add_stake_tx(
            rpc_url=rpc_url,
            chain_id=chain_id,
            private_key=private_key,
            amount_axon=amount,
            max_gas_gwei=max_gas_gwei,
            receipt_timeout_sec=receipt_timeout,
            dry_run=cfg["dry_run"],
        )

        if tx_result["ok"]:
            logger.info(
                "[%s] compound OK tx=%s amount=%.4f AXON",
                name, tx_result.get("tx_hash", ""), amount,
            )
        else:
            logger.error("[%s] compound FAILED: %s", name, tx_result.get("error"))
            had_error = True

        results.append({
            "agent": name,
            "action": "compound",
            "amount_axon": amount,
            "ok": tx_result["ok"],
            "tx_hash": tx_result.get("tx_hash"),
            "error": tx_result.get("error"),
            "dry_run": tx_result.get("dry_run", False),
        })

    print(json.dumps({"results": results, "had_error": had_error}, ensure_ascii=False, indent=2))
    logger.info("=== compound run end (agents=%d, errors=%s) ===", len(plans), had_error)
    return 1 if had_error else 0


# ── 状态检查（只查询，不发 TX）─────────────────────────────────────────────

def compound_status(state_file: str, network: str, agents: str) -> int:
    """
    打印所有 agents 的余额、质押、声誉和理论复投计划（不执行任何 TX）。
    """
    state = load_state(state_file)
    network_cfg = load_yaml(network)
    agents_cfg = load_yaml(agents)
    cfg = {**DEFAULT_COMPOUND_CFG, "dry_run": True}

    plans = build_compound_plan(state, agents_cfg, network_cfg, cfg)

    rows = []
    for p in plans:
        rows.append({
            "agent": p.get("agent_name", ""),
            "validator": p.get("is_validator", False),
            "balance_axon": p.get("balance_axon"),
            "stake_axon": p.get("stake_axon"),
            "reputation": p.get("reputation"),
            "action": p.get("action", ""),
            "compound_amount_axon": p.get("compound_amount_axon"),
            "mining_power_gain_pct": p.get("roi_info", {}).get("mining_power_gain_pct"),
            "contrib_cap_gain_pct": p.get("roi_info", {}).get("contribution_cap_gain_pct"),
            "reason": p.get("reason", ""),
        })

    print(json.dumps({"compound_plan": rows}, ensure_ascii=False, indent=2))
    return 0


# ── Daemon 循环 ───────────────────────────────────────────────────────────

def compound_daemon(
    state_file: str,
    network: str,
    agents: str,
    compound_config: str | None = None,
    dry_run: bool = False,
) -> int:
    """
    持续运行的 compound daemon。每隔 interval_sec 执行一次 compound_run_once。

    compound_config: 可选的 YAML 配置文件（覆盖默认值）
    """
    cfg = dict(DEFAULT_COMPOUND_CFG)
    if compound_config and os.path.exists(compound_config):
        try:
            extra = load_yaml(compound_config)
            cfg.update(extra.get("compound", extra))
            logger.info("loaded compound config from %s", compound_config)
        except Exception as e:
            logger.warning("failed to load compound config %s: %s", compound_config, e)

    if dry_run:
        cfg["dry_run"] = True

    interval = int(cfg.get("interval_sec", 7200))
    logger.info(
        "compound daemon starting: interval=%ds, dry_run=%s, min_compound=%.2f AXON",
        interval, cfg["dry_run"], cfg["min_compound_axon"],
    )

    while True:
        try:
            compound_run_once(state_file, network, agents, compound_cfg=cfg, dry_run=cfg["dry_run"])
        except Exception as e:
            logger.error("compound_run_once raised unexpected exception: %s", e, exc_info=True)

        logger.info("sleeping %d seconds until next compound run…", interval)
        time.sleep(interval)


# ── 声誉路径预测工具 ───────────────────────────────────────────────────────

def predict_reputation_path(
    current_l1: float = 0.0,
    current_l2: float = 0.0,
    is_validator: bool = False,
    challenge_top20: bool = False,
    epochs: int = 50,
) -> list[dict]:
    """
    预测未来 N 个 epoch 的声誉轨迹（用于规划）。

    基于 l1_reputation.go 的精确常量（来自源码）：
      +0.3 heartbeat (activity > 0)
      +0.5 on-chain active (activity >= 10)
      +2.0 AI challenge top 20%  (仅 validator)
      +1.0 AI challenge top 50%  (仅 validator，未进入 top 20%）
      +0.5 validator sign rate 80-95%（当前 proxy 公式实际无法触发，保守不计）
      -0.1 L1 decay per epoch
    """
    l1 = current_l1 * 1000  # to millis
    l2 = current_l2 * 1000

    L1_CAP = 40_000
    L2_CAP = 30_000
    TOTAL_MAX = 100_000

    path = []
    for epoch in range(epochs):
        total_millis = min(l1 + l2, TOTAL_MAX)
        legacy_rep = total_millis // 1000  # 0-100
        mp = calc_mining_power(100.0, int(legacy_rep))  # normalized at 100 AXON stake

        path.append({
            "epoch": epoch,
            "l1": round(l1 / 1000, 2),
            "l2": round(l2 / 1000, 2),
            "total": round(total_millis / 1000, 2),
            "legacy_rep_int": int(legacy_rep),
            "mining_power_at_100axon": round(mp, 4),
        })

        # epoch 增益
        delta_l1 = 300 + 500  # heartbeat + 10 txs active（正常运行假设）
        if is_validator:
            if challenge_top20:
                delta_l1 += 2000  # top 20% AI challenge
            else:
                delta_l1 += 1000  # top 50% AI challenge
        delta_l1 -= 100  # L1 decay
        delta_l2 = -50    # L2 decay only

        l1 = max(0, min(l1 + delta_l1, L1_CAP))
        l2 = max(0, l2 + delta_l2)

    return path


# ── CLI 入口 ──────────────────────────────────────────────────────────────

def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m scripts.compound",
        description="Axon Agent Auto-Compound Tool",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # ── status ──
    p_status = sub.add_parser("status", help="查询所有 agents 余额/质押/声誉，显示复投计划（不执行）")
    p_status.add_argument("--state", default="state/deploy_state.json")
    p_status.add_argument("--network", default="configs/network.yaml")
    p_status.add_argument("--agents", default="configs/agents.yaml")

    # ── run ──
    p_run = sub.add_parser("run", help="执行一次复投（查询余额 → 计算 → addStake TX）")
    p_run.add_argument("--state", default="state/deploy_state.json")
    p_run.add_argument("--network", default="configs/network.yaml")
    p_run.add_argument("--agents", default="configs/agents.yaml")
    p_run.add_argument("--config", default=None, help="可选 compound YAML 配置文件路径")
    p_run.add_argument("--dry-run", action="store_true", help="只计算，不发 TX")
    p_run.add_argument("--min-compound", type=float, default=None, help="覆盖 min_compound_axon")
    p_run.add_argument("--reserve", type=float, default=None, help="覆盖 reserve_axon")

    # ── daemon ──
    p_daemon = sub.add_parser("daemon", help="持续运行的 compound daemon")
    p_daemon.add_argument("--state", default="state/deploy_state.json")
    p_daemon.add_argument("--network", default="configs/network.yaml")
    p_daemon.add_argument("--agents", default="configs/agents.yaml")
    p_daemon.add_argument("--config", default=None, help="可选 compound YAML 配置文件路径")
    p_daemon.add_argument("--dry-run", action="store_true")

    # ── predict-rep ──
    p_rep = sub.add_parser("predict-rep", help="预测声誉增长曲线")
    p_rep.add_argument("--l1", type=float, default=0.0, help="当前 L1 分")
    p_rep.add_argument("--l2", type=float, default=0.0, help="当前 L2 分")
    p_rep.add_argument("--validator", action="store_true", help="是否为 validator（影响 challenge 加分）")
    p_rep.add_argument("--challenge-top20", action="store_true", help="AI challenge 是否进前 20%")
    p_rep.add_argument("--epochs", type=int, default=30)

    # ── roi ──
    p_roi = sub.add_parser("roi", help="计算追加质押的理论收益提升")
    p_roi.add_argument("--stake", type=float, required=True, help="当前质押（AXON）")
    p_roi.add_argument("--add", type=float, required=True, help="追加质押（AXON）")
    p_roi.add_argument("--rep", type=int, default=50, help="声誉值 (0-100)")
    p_roi.add_argument("--validator", action="store_true")

    args = parser.parse_args()

    if args.cmd == "status":
        return compound_status(args.state, args.network, args.agents)

    elif args.cmd == "run":
        extra: dict = {}
        if args.min_compound is not None:
            extra["min_compound_axon"] = args.min_compound
        if args.reserve is not None:
            extra["reserve_axon"] = args.reserve
        compound_cfg_override: dict | None = None
        if args.config:
            try:
                raw = load_yaml(args.config)
                compound_cfg_override = raw.get("compound", raw)
            except Exception as e:
                logger.error("Failed to load config %s: %s", args.config, e)
                return 2
        merged = {**DEFAULT_COMPOUND_CFG, **(compound_cfg_override or {}), **extra}
        return compound_run_once(args.state, args.network, args.agents, compound_cfg=merged, dry_run=args.dry_run)

    elif args.cmd == "daemon":
        return compound_daemon(args.state, args.network, args.agents, compound_config=args.config, dry_run=args.dry_run)

    elif args.cmd == "predict-rep":
        path = predict_reputation_path(
            current_l1=args.l1,
            current_l2=args.l2,
            is_validator=args.validator,
            challenge_top20=args.challenge_top20,
            epochs=args.epochs,
        )
        print(json.dumps({"reputation_path": path}, ensure_ascii=False, indent=2))
        return 0

    elif args.cmd == "roi":
        roi = calc_compound_roi(args.stake, args.add, args.rep, args.validator)
        print(json.dumps(roi, ensure_ascii=False, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
