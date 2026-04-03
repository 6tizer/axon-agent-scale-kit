# AXON Agent Scale Kit - Code Wiki

## 1. 项目整体架构 (Overall Architecture)
AXON Agent Scale Kit 是一个 CLI 优先的运维工具集，专为在 AXON 协议网络上规模化部署、管理和治理 AI Agent 设计。项目采用 Python 3.11+ 开发，通过集成 `eth-account` 以及封装官方 `axond` 二进制程序，实现与 EVM 和 Cosmos SDK 双层的交互。

核心架构理念：
- **状态单一事实来源 (Single Source of Truth)**：所有运行时的状态（包括分配的 Agent、钱包地址、私钥引用、注册与 Stake 证据等）统一存储在本地的 `state/deploy_state.json` 文件中。
- **无状态代理 (Stateless Agents)**：Agent 进程本身不需要复杂的配置，统一由系统级守护进程 `axon-heartbeat-daemon.service` 通过读取 state 文件进行集中式的心跳和生命周期管理。
- **1-Agent-1-Container 或守护进程编排**：支持在远程服务器上部署独立的 Agent 容器，或通过统一的 Daemon 批量处理心跳（如迁移后的 qqclaw-validator）。
- **流程化伸缩 (Scaling Pipeline)**：将繁杂的 Agent 创建流程拆分为请求 (Request) -> 计划 (Plan) -> 执行 (Execute) -> 状态报告 (Status) -> 修复 (Repair)。

## 2. 主要模块职责 (Main Module Responsibilities)

- **`scripts/axonctl.py`**：CLI 主入口文件。负责解析超过 30+ 种子命令，涵盖从钱包管理、配置校验、Scale 意图解析 (`run-intent`)、链上注册 (`register-onchain-once/batch`)、远程部署 (`remote-deploy`) 到生命周期报告和修复 (`lifecycle-report/repair`) 的所有核心运维逻辑。
- **`scripts/compound.py`**：自动复投守护进程。扫描所有 agent 的链上余额和质押信息，基于 ROI 计算决策是否将奖励复投回质押（`addStake` 交易）。支持 `status`（只查询不发 TX）、`run`（单次执行）、`daemon`（持续循环）、`roi`（离线 ROI 计算）、`predict-rep`（声誉路径预测）五个子命令。依赖 `web3` 库（生产服务器已安装）。
- **`scripts/axond_tx.py`**：`axond` CLI 子进程封装模块。专门用于处理需要 Cosmos SDK 签名的交易，特别是 AI Challenge 的 Commit (`MsgSubmitAIChallengeResponse`) 和 Reveal (`MsgRevealAIChallengeResponse`)，并支持 EVM 地址到 Cosmos Bech32 地址的转换。
- **`scripts/_shared_crypto.py`**：共享密码学工具模块。实现与 AXON 链上 Keeper 完全一致的 Hash 算法（如 `keeper_commit_hash`）以及字符串的 Normalize 逻辑，避免链上链下数据验证不一致。
- **`scripts/release_deploy_verify.sh`**：一键发布与部署脚本。集成了本地回归测试、Push 代码、远程服务器部署以及服务重启与状态验证的 CI/CD 流程。
- **`configs/`**：配置目录。包含全局的网络配置 `network.yaml`（RPC、Gas、心跳及 Challenge 规则）、Agent 声明文件 `agents.yaml`，以及复投守护进程配置 `compound.yaml`（最小复投量、保留量、最大单次复投量、间隔、Gas 上限）。实际运行时推荐使用不被 Git 追踪的 `configs/runtime/*.yaml`。
- **`state/`**：运行时状态目录。核心文件为 `deploy_state.json`，其中保存了敏感的钱包私钥和动态生成的伸缩计划与证据，绝对禁止提交到版本控制中。
- **`docs/`**：项目文档。包含核心的开发者参考 `DEVELOPER_REFERENCE.md` 以及协作流程规范 `ops/collaboration_workflow.md`。

## 3. 关键类与函数说明 (Key Classes and Functions)

### `scripts/axonctl.py`
- **`main()`**: CLI 程序的入口，基于 `argparse` 注册所有子命令路由。
- **`load_state(path) / save_state(path, state)`**: 负责读取和原子化安全写入（先写 `.tmp` 再重命名）全局状态文件 `deploy_state.json`，防止进程意外崩溃导致数据损坏。
- **`rpc_chain_id(rpc_url)`**: 发送原生的 `eth_chainId` JSON-RPC 请求，验证当前网络连通性。
- **`get_current_block_healthy(network_cfg)`**: 获取当前的 EVM 区块高度，并附带主/备 RPC 节点的健康度对比与降级容灾逻辑。

### `scripts/axond_tx.py`
- **`class AxondClient`**: `axond` CLI 封装客户端，在 `challenge_run_once()` 的 command 模式下被调用。自动从 `deploy_state.json` 加载对应 Agent 的私钥，并执行交易：
  - **`submit_commit(agent_name, epoch, commit_hash)`**: 构造并广播 Commit 交易。
  - **`submit_reveal(agent_name, epoch, answer)`**: 构造并广播 Reveal 交易，附带 512 字节最大长度检查。
  - **`query_current_challenge()`**: 跨多种 API 路径（标准 Cosmos REST 或 Axon 自定义 API）轮询并解析当前活跃的 AI Challenge 状态。
- **`evm_to_bech32(evm_address)`**: 借助 `axond debug addr`，将 `0x` 开头的 EVM 格式地址转换为 `axon1` 开头的 Cosmos 原生地址。
- **`query_tx_status(tx_hash) / wait_for_tx(...)`**: 根据 Cosmos SDK API 轮询交易的确认状态（基于 `code` 和 `height` 验证）。

### `scripts/_shared_crypto.py`
- **`keeper_commit_hash(cosmos_address, answer)`**: 生成验证用的 Hash，直接采用 `SHA256(bech32_addr + ":" + raw_answer)`。
- **`go_normalize(text)`**: 模拟 Go 语言的文本归一化逻辑，去除空格、Tab 及换行并转为小写。

## 4. 依赖关系 (Dependencies)

### 环境与语言
- **Python**: `>= 3.10`（推荐 3.11），因代码中大量使用了 `int | None` 这样的 Union Type 语法，不兼容 3.9。
- **OS**: 兼容 Linux/macOS，由于需在服务器上部署 Systemd 服务，生产环境强依赖 Ubuntu/Linux。

### 核心 Python 包 (`requirements.txt`)
- `PyYAML==6.0.2`: 解析 `network.yaml` 与 `agents.yaml`。
- `eth-account==0.13.3`: 用于在本地生成真实的 Funding 钱包和 Agent 钱包私钥。

### 可选依赖（生产服务器已安装，本地开发可选）
- `web3`: `compound.py` 用于查询链上余额/质押/声誉，以及构造和发送 `addStake` EVM 交易。未安装时 `compound.py status` 会在所有 agent 返回 `"reason": "web3 not installed"`。

### 外部二进制与服务依赖
- **`axond` 二进制**: AXON 官方节点程序。依赖其进行离线密钥管理（`axond keys import`）和交易签名广播。
- **Systemd**: 生产服务器上依赖 `axon-heartbeat-daemon.service` 等守护进程维持 Agent 心跳。
- **Docker**: 对于单 Agent 容器化部署模式，依赖目标服务器具备 Docker 运行环境。

## 5. 项目运行方式 (How to Run)

### 5.1 环境初始化
```bash
# 1. 创建并激活虚拟环境 (需 Python 3.11)
python3.11 -m venv .venv
source .venv/bin/activate

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 初始化本地依赖与检查
python scripts/axonctl.py init-step --mode local
```

### 5.2 基础配置与钱包生成
在 `configs/runtime/` 下配置私有的网络与主机信息，并生成全局 Funding 钱包：
```bash
# 生成接收 AXON 转账的 Funding 钱包
python scripts/axonctl.py wallet-generate --role funding --label "my-funding"
```

### 5.3 自动化 Scale 流程
执行一条基于自然语言的 Scale Intent：
```bash
# 校验配置
python scripts/axonctl.py validate --network configs/network.yaml --agents configs/agents.yaml

# 生成计划并执行扩容 (含注册、打款、分配钱包)
python scripts/axonctl.py run-intent \
  --network configs/network.yaml \
  --agents configs/agents.yaml \
  --intent "I fund 250 AXON, scale 2 agents"
```

### 5.4 远程部署与监控
将状态推送到远程服务器，并启动/检查 Agent：
```bash
# 部署至远程主机
python scripts/axonctl.py remote-deploy \
  --state-file state/deploy_state.json \
  --request-id <request_id> \
  --hosts configs/runtime/hosts.runtime.yaml \
  --host your-server \
  --network configs/network.yaml \
  --agents configs/agents.yaml

# 检查生命周期与 Agent 健康度
python scripts/axonctl.py lifecycle-report --network configs/network.yaml --request-id <request_id>
```

### 5.5 AI Challenge 与心跳
在本地或服务器上触发批量心跳和 Challenge 答题：
```bash
# 发送心跳
python scripts/axonctl.py heartbeat-batch --network configs/network.yaml --request-id <request_id>

# 参与 AI Challenge
python scripts/axonctl.py challenge-batch --network configs/network.yaml --request-id <request_id>
```

### 5.6 自动复投（Auto-Compound）
查询所有 agent 状态并决策复投计划（不发 TX）：
```bash
python3 scripts/compound.py status \
  --state state/deploy_state.json \
  --network configs/network.yaml \
  --agents configs/agents.yaml

# 单次执行复投（实际发 TX）
python3 scripts/compound.py run \
  --state state/deploy_state.json \
  --network configs/network.yaml \
  --agents configs/agents.yaml \
  --config configs/compound.yaml

# 离线 ROI 计算（无需连链）
python3 scripts/compound.py roi --stake 8591 --add 50 --rep 50 --validator

# 声誉增长路径预测
python3 scripts/compound.py predict-rep --l1 20 --epochs 30
```

持续运行守护进程请使用 `scripts/systemd/axon-compound-daemon.service`（部署步骤见 `docs/ops/roadmap.md §十一.4`）。

## 6. 协作开发规范 (Collaboration Workflow)
- **Fork + PR 模式**：协作者必须将仓库 Fork 到自己的 GitHub，所有功能开发必须通过提交 Pull Request 到主仓库 (`6tizer/axon-agent-scale-kit`) 的 `main` 分支。
- **保护 Main 分支**：远程 Server 永远且仅拉取 `main` 分支的代码，禁止在 Server 上进行直接的代码修改或切换分支。
- **发布流程**：通过内置的 `scripts/release_deploy_verify.sh` 一键完成回归测试、Push、部署以及重启服务验证。
