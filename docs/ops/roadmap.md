# Axon 运维路线图 & 架构备忘

> 最后更新：2026-04-03
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

### 🔴 P0 — 等待中（被动）

**节点同步完成**

- 背景：v1.1.0 升级（block 259051）导致旧节点崩溃，已升级二进制并从高度 0 重新同步
- 目标高度：~267,000+
- 进度：2026-04-03 约 02:30 开始，预计 03:00-05:00 完成
- 验证命令：
  ```bash
  curl -s http://localhost:26657/status | python3 -c 'import sys,json; d=json.load(sys.stdin); si=d["result"]["sync_info"]; print("Height:", si["latest_block_height"], "catching_up:", si["catching_up"])'
  ```
- 完成标志：`catching_up: False`，之后可在 [axonrep.xyz](https://axonrep.xyz) 验证者排行看到签名状态变绿

### 🟠 P1 — 节点同步完成后立刻做

**切换为 `start_validator_node.sh` 配置（同台服务器）**

- 理由：当前全节点配置（`pruning=custom`，保留历史数据，全开 API）比验证者配置重得多，磁盘和内存消耗更高
- 效果：`pruning=everything`，关闭外部 API/gRPC/JSON-RPC，磁盘占用大幅减少（预计从 20%+ 降至 <10%）
- **注意**：操作时必须先彻底停止现有节点，再用新脚本启动，防止数据目录冲突
- 操作步骤：
  ```bash
  # 1. 停止现有节点
  bash /opt/axon-node/start_sync_node.sh stop

  # 2. 确认进程已死
  ps aux | grep axond | grep -v grep | grep -v bash

  # 3. 用 validator 脚本启动（不需要 init，密钥已存在）
  KEYRING_PASSWORD_FILE=/opt/axon-node/keyring.pass \
    nohup bash /opt/axon-node/start_validator_node.sh start > /tmp/axond_validator.log 2>&1 &

  # 4. 验证
  tail -f /tmp/axond_validator.log
  ```
- **双签风险提醒**：绝对不能同时运行两个持有相同私钥的 axond 进程，否则触发双签 → 罚没 5% 质押（430 AXON），永久关押

### 🟡 P2 — 可并行进行（不依赖节点同步）

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

## 四、今日操作记录（2026-04-03）

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

## 七、有用的快速检查命令

```bash
# 节点同步进度
curl -s http://localhost:26657/status | python3 -c 'import sys,json; d=json.load(sys.stdin); si=d["result"]["sync_info"]; print("Height:", si["latest_block_height"], "catching_up:", si["catching_up"])'

# 验证者链上状态
curl -s https://mainnet-api.axonchain.ai/cosmos/staking/v1beta1/validators/axonvaloper14xxu9g0fvnkclwt98yz9cldtwhpam560sgc8s0 | python3 -c 'import sys,json; v=json.load(sys.stdin)["validator"]; print("moniker:", v["description"]["moniker"], "status:", v["status"], "jailed:", v["jailed"], "tokens:", int(v["tokens"])/1e18, "AXON")'

# daemon 状态
systemctl is-active axon-heartbeat-daemon.service axon-challenge-daemon.service

# 磁盘和内存
df -h / | tail -1
ps aux | grep axond | grep -v grep | grep -v bash | awk '{print "RSS:", $6/1024"MB"}'

# challenge 日志
journalctl -u axon-challenge-daemon.service -n 30 --no-pager | grep -E 'commit|reveal|epoch|ok|error'
```
