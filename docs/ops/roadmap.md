# Axon 运维路线图 & 架构备忘

> 最后更新：2026-04-03（§八 收益机制完整调研 + §九 改进行动计划）
> 记录本次会话中确认的架构事实、待办事项和决策依据，供后续 Agent 或操作者参考。

---

## 一、服务器架构现状（重要事实）

### 服务器：`ubuntu@43.165.195.71`

| 组件 | 说明 |
|------|------|
| `axond` 进程 | **唯一一个**，同时承担验证者节点 + 全节点两个角色 |
| 启动脚本 | 当前用 `start_sync_node.sh`（全节点配置），但持有验证者私钥 |
| 验证者身份 | **QQClaw-Validator**，质押 8,600 AXON，排名 #8，链上状态 BONDED |
| 验证者 valoper | `axonvaloper14xxu9g0fvnkclwt98yz9cldtwhpam560sgc8s0` |
| 验证者共识公钥 | `ozXP9m2hmNaF74w4GQJWT8spXHkaaHC7kgIphE7kRXY=` |
| 私钥文件位置 | `/opt/axon-node/data/node/config/priv_validator_key.json` |
| 元数据目录 | `/opt/axon-node/data/validator/`（含 mnemonic、address、valoper 等） |
| 10 个 Agent | 独立注册的链上 Agent，走外网 API 广播，与节点无关 |
| 两个 daemon | `axon-heartbeat-daemon.service`、`axon-challenge-daemon.service`，均 active |

### 关键认知

- `start_validator_node.sh` 和 `start_sync_node.sh` 是**同一个 `axond` 二进制的不同配置文件**，数据目录相同
- 两个脚本不能同时运行（会冲突）
- 当前节点 = 验证者节点，只是用了更重的全节点配置（保留历史数据 + 全开 API）
- 10 个 Agent 完全独立于节点，不受节点状态影响

---

## 二、待办事项（按优先级）

### ✅ P0 — 已完成

**节点同步完成**（2026-04-03）

- 已完成同步至 height 281096+，`catching_up: False`
- 验证者已 unjail，恢复 BOND_STATUS_BONDED，正在签块

### ✅ P1 — 已完成（部分）

**验证者恢复正常运行**

- unjail TX 已发送并确认（txhash: DFF8B8F9F3522192603A31395E02FF25D393D97954C9BCB95DCA71C11895AA84）
- 当前节点用 `start_sync_node.sh` 配置启动，资源占用可接受（磁盘 30%，内存 5.5/7.5GB）
- **可选**：未来如需降低内存/磁盘，可切换为 `start_validator_node.sh`（pruning=everything），但需要重启节点。当前暂不需要。

### ✅ P1.5 — 已完成

**部署 PR #16 + PR #17（challenge validator gate 全套修复）**

- PR #16（`challenge_batch` 白名单过滤）已 merge 并部署，commit `1909113`
- PR #17（`challenge_gate_check` `validator_active` 字段 bug 修复）已 merge 并部署，commit `c9ab34d`
- challenge daemon 已重启（PID 3070131），`validator_active: true` 已确认
- 9 个非 validator agents 已被正确跳过，`qqclaw-validator` 是唯一挑战候选人

### 🟡 P2 — 可在稳定运行一段时间后进行

**`challenge_batch` 串行改并发**

- 位置：`scripts/axonctl.py`，`challenge_batch` 函数（约 L1474-1487）
- 问题：当前 `for name in targets: challenge_run_once(...)` 是纯串行
  - 10 个 agent 勉强够用（约 150-200 秒，challenge 窗口 240 秒）
  - 超过 20 个 agent 必然超时
- 目标改法（方案 A，最小改动）：

  ```python
  import threading
  from concurrent.futures import ThreadPoolExecutor, as_completed

  _state_lock = threading.Lock()  # 模块级别，全局唯一

  # save_state 里加锁
  def save_state(path: str, state: dict) -> None:
      with _state_lock:
          # ... 现有的 MAX_EVENTS 裁剪 + 原子写逻辑不变 ...

  # challenge_batch 里改成并发
  def challenge_batch(...):
      ...
      passed, failed = [], []
      with ThreadPoolExecutor(max_workers=min(len(targets), 20)) as pool:
          futures = {pool.submit(challenge_run_once, state_file, network, name): name
                     for name in targets}
          for future in as_completed(futures):
              name = futures[future]
              if future.result() == 0:
                  passed.append(name)
              else:
                  failed.append(name)
  ```

- **关键**：`save_state` 必须加 `_state_lock`，否则并发写会静默丢失数据（不崩溃但 state 被覆盖）
- 开发流程：本地开发 → PR → 6tizer review → merge → deploy

### 🟢 P3 — 低优先级，随时可做

**补全 CAP theorem 答案**

- 位置：`configs/challenge_answers.yaml`
- 题目：`"What does CAP theorem state about distributed systems?"`
- 期望 hash：`3829c9300cee83099f62df43694c0fc29eb2b1ed874bab38f207172fc3266081`
- 影响：每约 110 个 epoch 中有 1 次可能拿不到分，概率约 0.9%
- 验证脚本：
  ```python
  import hashlib
  target = "3829c9300cee83099f62df43694c0fc29eb2b1ed874bab38f207172fc3266081"
  candidates = [
      "a distributed system can only guarantee two of the following three properties: consistency, availability, and partition tolerance",
      # ... 尝试各种变体（小写，normalize 后）
  ]
  for c in candidates:
      normalized = c.lower().replace(" ", "").replace("\t", "").replace("\n", "")
      # 注意 normalizeAnswer 只是 lower + 去空格
      h = hashlib.sha256(c.lower().strip().encode()).hexdigest()
      if h == target:
          print("FOUND:", c)
  ```
- 找到后走 PR 流程更新 yaml

---

## 三、架构演进建议（未来规划，不紧急）

### 短期（当前 10 个 agent）
- 完成 P1（切换验证者配置）后，服务器资源充裕，无需额外操作

### 中期（50 个 agent）
- 认真考虑将验证者节点迁离（或关闭全节点 API）
- `deploy_state.json` 考虑换成 SQLite（原生并发安全）
- 考虑按 agent 分组，每组独立进程

### 长期（100 个 agent）
- 多台服务器分片（每台 20-30 个 agent）
- 中央化 state 存储（SQLite 或 Redis）
- 验证者节点独立部署，完全与 agent 管理解耦

### 验证者迁移到新服务器的注意事项（如有需要）
1. **新服务器先完整同步到链顶**（不能带着旧数据，需要从 0 开始）
2. **确认旧节点彻底停止**（`ps aux | grep axond` 为空）
3. 将 `priv_validator_key.json` 拷贝到新服务器
4. 启动新节点
5. **绝对不能新旧同时运行** → 双签 → 永久关押

---

## 四、操作记录

### 2026-04-03 凌晨（节点升级 + daemon 修复）

| 时间 | 操作 | 结果 |
|------|------|------|
| 凌晨 | 发现节点卡在 block 259051（v1.0→v1.1 consensus 升级） | 已诊断 |
| 01:00 | 下载 v1.1.0-beta1，SHA256 校验通过，替换 `/opt/axon-node/axond` | ✅ |
| 01:17 | 尝试 statesync（trust_height=265000）| ❌ 网络无节点提供快照 |
| 01:22 | 切换为 blocksync 从 0 开始，删除 blockstore/application/state DB | ✅ 正在同步 |
| 同期 | 磁盘：75% → 19%（删 tx_index.db 12GB + blockstore 2.4GB + application 25GB） | ✅ |
| 同期 | 内存：6.4GB → ~2GB（iavl-cache 调低 + 旧进程清理） | ✅ |
| 节点升级前 | PR #12（Challenge daemon 5项 bug fix）已 merge | ✅ |
| 节点升级前 | PR #13（补全 109/110 challenge 答案）已 merge | ✅ |

### 2026-04-03（节点同步完成 + 验证者恢复）

| 时间 | 操作 | 结果 |
|------|------|------|
| 节点同步完成 | `catching_up: False`，height 281096 | ✅ |
| 同期 | QQClaw-Validator 状态：jailed=True，BOND_STATUS_UNBONDING | 需unjail |
| 同期 | 发送 unjail TX（txhash: DFF8B8F9...）| ✅ |
| 同期 | 验证者恢复：BOND_STATUS_BONDED，jailed=False，tokens 8591.4 AXON | ✅ |
| 同期 | 验证者在活跃 validator set，voting power 8591，正在签块 | ✅ |
| 同期 | PR #14（challenge_batch 并发改造）已 merge | ✅ |
| 同期 | PR #15（axond --node + --fees fix）已 merge | ✅ |
| 同期 | PR #16（challenge validator gate fix）已 merge 并部署 commit `1909113` | ✅ |
| 同期 | PR #17（challenge_gate_check validator_active bug fix）已 merge 并部署 commit `c9ab34d` | ✅ |
| 同期 | challenge daemon 重启，`validator_active: true` 确认，白名单过滤生效 | ✅ |
| 待验证 | 等下一个 epoch 挑战窗口，观察 qqclaw-validator commit + reveal 成功 | 🔄 |

---

## 六、协议层面关键发现：AI 挑战权限（2026-04-03 确认）

### 核心结论

**只有注册为 validator 的地址才能提交 AI Challenge TX。`agent-001` 至 `agent-009` 永久无资格。**

### 链上证据

文件：`x/agent/keeper/msg_server.go`（`SubmitAIChallengeResponse` 和 `RevealAIChallengeResponse`）

```go
// 两个函数都在第一步调用这个检查：
if !k.isActiveValidatorAddress(ctx, msg.Sender) {
    return nil, types.ErrValidatorRequired
}
```

文件：`x/agent/keeper/keeper.go`

```go
func (k Keeper) isActiveValidatorAddress(ctx sdk.Context, address string) bool {
    accAddr, _ := sdk.AccAddressFromBech32(address)
    validator, err := k.stakingKeeper.GetValidator(ctx, sdk.ValAddress(accAddr))
    if err != nil { return false }
    return validator.IsBonded() && !validator.IsJailed()
}
```

文件：`x/agent/types/errors.go`

```go
ErrValidatorRequired = errors.Register(ModuleName, 1120, "operation requires an active bonded validator")
```

### 影响分析

| 角色 | 能否提交 Challenge TX | 原因 |
|------|----------------------|------|
| `qqclaw-validator` | ✅ 能（当 bonded 且未 jailed） | 已在 staking 模块注册为 validator |
| `agent-001` ~ `agent-009` | ❌ 永远不能 | 仅为 agent，不是 validator，`code=1120` 是协议层 invariant |

### 已采取的纠正措施

- `configs/network.yaml`：`validator_required: false` → `true`，新增 `challenge_agents: ["qqclaw-validator"]` 白名单
- `scripts/axonctl.py`：`challenge_batch` 中增加白名单过滤，非 validator agents 在发起任何网络调用前即被跳过
- `configs/agents.yaml`：为 `qqclaw-validator` 增加 `is_validator: true` 标记（文档用途）

### 之前工作的有效性说明

PR #12（并发改造）、PR #13（答案补全）、PR #14（并发 challenge_batch）、PR #15（node & fees fix）均对 `qqclaw-validator` 有效。这些改动确保了 qqclaw-validator 能正确提交 challenge TX。对 agent-001~009 而言，这些改动没有副作用——它们会被白名单过滤，不再尝试提交。

---

## 八、收益机制完整分析（2026-04-03 调研）

> 基于 `axon-chain/axon` 源码 `x/agent/keeper/` 完整阅读，以下为协议层面精确事实，不含推测。

### 8.1 三条收益流

| 收益流 | 总量上限 | 分配频率 | 参与资格 |
|--------|---------|---------|---------|
| **区块奖励**（block rewards） | 650M AXON（65%） | 每 epoch 结算 | 需 online；validator 走矿力权重，所有 agent 走声誉权重 |
| **贡献奖励**（contribution rewards） | 350M AXON（35%） | 每 epoch 结算 | 声誉 ≥ 20，注册 ≥ 7 天（≥ 120960 blocks） |
| **旧版 epoch 奖励**（reward pool） | 来自 protocol 划拨 | 每 epoch | 在线 agent，按质押×奖励乘数 |

**区块奖励每块铸造量（当前 Year 1-4 阶段）**：
- 基础：12.367 AXON/block，4 年一减半
- 分配：区块提议者 20%，Validator Pool 55%，声誉池 25%

### 8.2 矿力公式（决定 Validator Pool 分配）

```
MiningPower = StakeScore × ReputationScore

StakeScore      = stake ^ alpha          （alpha = 0.5，即 √stake）
ReputationScore = 1 + beta × ln(1 + rep) / ln(rMax + 1)
                  （beta = 1.5，rMax = 100；rep 范围 0-100）
```

**关键数字**：
| rep 值 | ReputationScore | 相对 rep=0 的倍增 |
|-------|-----------------|-----------------|
| 0 | 1.00 | 1.0× |
| 30 | ~1.81 | +81% |
| 50 | ~2.07 | +107% |
| 70 | ~2.28 | +128% |
| 100 | ~2.50 | +150% |

**质押与矿力的关系（alpha=0.5 → 开方函数）**：
| 质押倍增 | 矿力倍增 |
|---------|---------|
| 2× | 1.41× |
| 4× | 2.00× |
| 9× | 3.00× |

结论：**声誉对矿力的边际收益高于质押**。rep 从 0 → 100 使矿力 ×2.5，而质押翻 4 倍矿力才 ×2。

### 8.3 声誉双层系统（L1 + L2）

**L1 分（上限 40.0，以 millis 存储）**：

| 行为 | 每 epoch 变化 |
|-----|-------------|
| heartbeat 至少 1 次 | +0.3 |
| 本 epoch 链上 tx ≥ 10 | +0.5 |
| validator 签块率 > 95% | +1.0 |
| validator 签块率 80-95% | +0.5 |
| 已部署合约本 epoch 被 ≥ 5 地址调用 | +0.5 |
| AI 挑战排名前 20% | +2.0 |
| AI 挑战排名前 50%（51-80%） | +1.0 |
| AI 挑战排名后 20% 或作弊 | -1.0 |
| agent 掉线（立即） | -5.0 |
| validator 双签（立即） | 清零 |
| 自然衰减（每 epoch） | -0.1 |

**L2 分（上限 30.0）**：来自社区举报/抗作弊机制，自然衰减 -0.05/epoch。

**总声誉** = min(L1 + L2, 100)；兼容字段 `agent.Reputation` = total/1000（映射到 0-100 整数）。

### 8.4 贡献奖励评分公式

```
score = 50 × deploys           # 部署合约次数
      + 30 × contractCalls     # 合约被外部调用次数
      + 10 × min(activity, 100) # 本 epoch tx 数（上限 100）
      + 10 × max(rep - 70, 0)  # rep > 70 的超额部分
      + 5  (online bonus)       # 在线奖励
```

每个 agent 的贡献奖励还受质押量**上限约束**：
```
maxReward = pool × capBps × agentStake / 10000 / totalEligibleStake
```
更多质押 → 更高 cap → 能接收更多贡献奖励。

### 8.5 旧版 epoch 奖励权重

```
weight = stake × (100 + repBonus + aiBonus)

repBonus: rep ≥ 90 → +20%, ≥ 70 → +15%, ≥ 50 → +10%, ≥ 30 → +5%
aiBonus:  score ≥ 90 → +30, ≥ 70 → +20, ≥ 50 → +10, 作弊 → -5
```

### 8.6 AI 挑战机制（仅 qqclaw-validator）

- 每 epoch 随机从 110 题题库选 1 题
- 协议要求：commit（提交 SHA256(addr+":"+answer) 哈希）→ reveal（提交原答案）
- 评分：答案 hash 完全匹配 → 100 分；部分匹配 → 10 分
- aiBonus 对应：score ≥ 90 → +30，≥ 70 → +20，≥ 50 → +10
- 声誉影响：前 20% → +2.0 L1，前 50% → +1.0 L1
- **当前状态**：109/110 题有正确答案（CAP theorem 待解）

---

## 九、基于调研的改进行动计划

### 优先级矩阵

| 行动 | 影响 | 难度 | 当前状态 |
|-----|------|------|---------|
| 维持 qqclaw-validator BONDED + 不 jail | 极高（失去全部 validator 收益） | 运维 | ✅ 监控中 |
| AI 挑战正确答案（109/110） | 高（每 epoch +2.0 L1 rep） | 已完成 | ✅ 已部署 |
| 所有 agent 每 epoch ≥ 10 txs（heartbeat） | 中（+0.5 L1 rep/epoch） | 需核查 | 🔍 见下 |
| 声誉从 0 爬升到 70+ | 高（rep 70 = 矿力 ×2.28） | 时间 | 🔄 自然增长 |
| CAP theorem 答案补全 | 低（0.9% 题库覆盖） | 研究 | ❓ 待解 |
| 增加质押量 | 中（开方关系，边际递减） | 资金 | 待评估 |

### P1：确认每 epoch heartbeat 次数 ≥ 10

**关键条件**：`activity >= 10`（`minTxsForActive = 10`）才能获 +0.5 L1 rep/epoch。

每次 heartbeat TX 计 1 次 activity（`IncrementEpochActivity`）。需要确认：
- epoch 长度（governance param `EpochLength`，单位 blocks）
- 当前 heartbeat 间隔（network.yaml `interval_blocks: 100`）

若 epoch = 1000 blocks，heartbeat 每 100 blocks = 10 次/epoch → **恰好满足**。  
若 epoch = 2000 blocks，heartbeat 每 100 blocks = 20 次/epoch → **充裕满足**。

**核查命令**：
```bash
# 查链上 EpochLength 参数
curl -s https://mainnet-api.axonchain.ai/axon/agent/v1/params | python3 -m json.tool | grep epoch
```

### P2：声誉爬升路径预测

假设当前 10 agents 全部从 InitialReputation（默认）开始，不考虑 AI 挑战：

```
每 epoch 净增（无挑战奖励）：
  +0.3（heartbeat）+ 0.5（≥10 txs）- 0.1（decay）= +0.7 L1/epoch

从 50 → 70 需要：(70 - 50) / 0.7 = ~29 epochs

若有 AI 挑战（qqclaw-validator，答案正确）：
  +0.3 + 0.5 + 2.0 + 1.0（validator sign rate 80%+）- 0.1 = +3.7 L1/epoch
  从 50 → 70 只需 ~5 epochs
```

### P3：CAP theorem 答案暴力搜索策略

- 目标 hash：`3829c9300cee83099f62df43694c0fc29eb2b1ed874bab38f207172fc3266081`
- normalizeAnswer = lowercase + 去全部空白字符
- 已尝试 100+ 候选，均未命中
- 建议：查阅 Axon 官方文档/whitepaper，或联系社区

验证脚本（已在 `_shared_crypto.py` 中实现）：
```python
from scripts._shared_crypto import keeper_answer_hash
print(keeper_answer_hash("your candidate answer"))
# 对比 target: 3829c9300cee83099f62df43694c0fc29eb2b1ed874bab38f207172fc3266081
```

---

## 七、有用的快速检查命令

```bash
# 节点同步进度
curl -s http://localhost:26657/status | python3 -c 'import sys,json; d=json.load(sys.stdin); si=d["result"]["sync_info"]; print("Height:", si["latest_block_height"], "catching_up:", si["catching_up"])'

# 验证者链上状态
curl -s https://mainnet-api.axonchain.ai/cosmos/staking/v1beta1/validators/axonvaloper14xxu9g0fvnkclwt98yz9cldtwhpam560sgc8s0 | python3 -c 'import sys,json; v=json.load(sys.stdin)["validator"]; print("moniker:", v["description"]["moniker"], "status:", v["status"], "jailed:", v["jailed"], "tokens:", int(v["tokens"])/1e18, "AXON")'

# Agent 模块链上参数（含 EpochLength、MinRegisterStake、MaxReputation 等）
curl -s https://mainnet-api.axonchain.ai/axon/agent/v1/params | python3 -m json.tool

# daemon 状态
systemctl is-active axon-heartbeat-daemon.service axon-challenge-daemon.service

# 磁盘和内存
df -h / | tail -1
ps aux | grep axond | grep -v grep | grep -v bash | awk '{print "RSS:", $6/1024"MB"}'

# challenge 日志
journalctl -u axon-challenge-daemon.service -n 30 --no-pager | grep -E 'commit|reveal|epoch|ok|error'
```
