# AXON 生产快照（只读）

- 采集时间（本地）：`2026-03-25 18:23:30 CST`
- 本地仓库：`/Users/mac-mini/Documents/Codex/axon-agent-scale-kit`
- 本地分支/提交：`main` / `abcdea3`
- 远端同步：`HEAD == origin/main`

## 1. 服务器连通与服务状态

命令：

```bash
ssh -i /Users/mac-mini/AXON-Chain/server/config/QQClaw.pem ubuntu@43.165.195.71 \
  'date "+%Y-%m-%d %H:%M:%S %Z"; hostname; whoami; \
   systemctl is-active axon-heartbeat-daemon.service; \
   systemctl is-active axon-agent-qqclaw.service'
```

输出：

```text
2026-03-25 18:23:35 CST
VM-0-13-ubuntu
ubuntu
active
active
```

## 2. Docker 运行态

命令：

```bash
ssh -i /Users/mac-mini/AXON-Chain/server/config/QQClaw.pem ubuntu@43.165.195.71 \
  'docker ps --format "{{.Names}}|{{.Status}}|{{.Image}}" | sort'
```

输出：

```text
axon-agent-agent-001|Up 8 hours|python:3.11-slim
axon-agent-agent-002|Up 8 hours|python:3.11-slim
axon-agent-agent-003|Up 8 hours|python:3.11-slim
axon-agent-agent-004|Up 8 hours|python:3.11-slim
axon-agent-agent-005|Up 8 hours|python:3.11-slim
axon-agent-agent-legacy-006|Up 4 hours|python:3.11-slim
axon-agent-agent-legacy-007|Up 4 hours|python:3.11-slim
axon-agent-agent-legacy-008|Up 4 hours|python:3.11-slim
axon-node|Up 6 days|debian:trixie-slim
```

## 3. Lifecycle 健康报告

命令：

```bash
ssh -i /Users/mac-mini/AXON-Chain/server/config/QQClaw.pem ubuntu@43.165.195.71 \
  'python3 /home/ubuntu/axon-agent-scale/scripts/axonctl.py lifecycle-report \
    --state-file /home/ubuntu/axon-agent-scale/state/deploy_state.json \
    --network /home/ubuntu/axon-agent-scale/configs/network.yaml'
```

核心结果：

```json
{
  "ok": true,
  "summary": {
    "HEALTHY": 8,
    "DEGRADED": 0,
    "FAILED": 0
  },
  "current_block": 137336
}
```

结论：

- 生产守护正常在线；
- 当前纳管 8 个 agent 全健康；
- 可作为本周后续变更的回归基线。
