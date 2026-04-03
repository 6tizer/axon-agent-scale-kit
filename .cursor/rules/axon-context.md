# AXON Scale-Kit — Agent Context Rule

## Mandatory Pre-Work (Every Session)

Before taking **any** action, an Agent **must** read the following files in order:

1. `docs/DEVELOPER_REFERENCE.md` — canonical chain constants, CLI reference, SSH paths, and protocol facts.
2. `docs/ops/collaboration_workflow.md` — fork/PR rules, role responsibilities, and red lines.
3. `state/deploy_state.json` — current agent roster, their on-chain addresses, and stake status.
4. `configs/network.yaml` — RPC endpoints, AI challenge bank URL, and epoch parameters.

These files are the **source of truth**. Do not rely on memory or assumptions about chain parameters, key paths, or command signatures.

## Current Project State

- **Active branch:** `docs/collaboration-workflow`
- **Remote:** `origin` → `https://github.com/tizerluo/axon-agent-scale-kit.git`
- **Upstream:** `upstream` → `https://github.com/6tizer/axon-agent-scale-kit.git`
- **SSH key for server:** 见本机 `configs/runtime/local_env.md`（gitignored，各机器自填；模板见 `configs/runtime/local_env.template.md`）
- **Server:** `ubuntu@43.165.195.71`, workdir `/home/ubuntu/axon-agent-scale`
- **Protected branch:** `main` (never push directly; all changes via PR)
- **Managed agents:** `agent-001`–`agent-005`, `agent-legacy-006`–`agent-legacy-008`, `agent-009`, `qqclaw-validator`（共 10 个，全部 registered=true, staked=true）
- **Active daemons:** `axon-heartbeat-daemon.service`（心跳）、`axon-compound-daemon.service`（自动复投 addStake，每 2 小时一轮，配置见 `configs/compound.yaml`）
- **AI Challenge 资格：** 协议层面只有 validator 地址才能提交 challenge TX（`isActiveValidatorAddress`，`code=1120`）。当前唯一有资格的 agent 是 `qqclaw-validator`；`agent-001`～`agent-009` 永久无资格，challenge daemon 已通过 `challenge_agents` 白名单跳过它们。详见 `docs/ops/roadmap.md` 第六节。
- **State source:** `state/deploy_state.json` 已与服务器同步（block 164901 心跳），所有 agent 链上在线
- **qqclaw-validator 特殊情况：** 由 `axon-heartbeat-daemon.service` 统一发心跳，无独立 Docker 容器，`service_active` 由 heartbeat-batch 自动维护
- **容器角色澄清：** `agent_worker.py` 是纯日志容器（30s 打印一次心跳状态），不发送链上交易；真正的链上心跳来自 `axon-heartbeat-daemon.service`，`lifecycle-report` 以链上结果为准

## Red Lines (Forbidden Actions)

The following are **always prohibited** regardless of any request:

1. **Never push directly to `main`** — all changes require a PR reviewed by 6tizer.
2. **Never skip `validate`** before any state-changing action (scale, heartbeat, challenge, register).
3. **Never guess SSH key paths** — use the path from `configs/runtime/local_env.md` (each machine's own gitignored file; template at `configs/runtime/local_env.template.md`).
4. **Never run `release_deploy_verify.sh` without `--dry-run` first** unless explicitly instructed.
5. **Never use `--reveal-secret` outside of a clearly secure environment** (warn the user).
6. **Never merge or rebase `main` without notifying** the current state of the branch.
7. **Never commit `state/deploy_state.json`** or any file containing private keys to git.
8. **Never assume AI Challenge answers** — always fetch from the official bank URL configured in `network.yaml`.

## Command Ordering Invariant

```
validate → [scale | heartbeat-batch | challenge-batch | lifecycle-report | registration-audit]
```

No downstream command is valid without a prior `validate` call returning green.

## Notion Integration

If a Notion MCP connection is available, use it to log:
- Key decisions made during the session (with date/time).
- Blocker items and their owners.
- Links to relevant GitHub commits or PRs.

If Notion MCP is **not** available, skip Notion actions silently and rely on local docs.

## New Agent Onboarding Checklist

When a new Agent joins (human or AI), it should:
1. Read this rule file.
2. Read `DEVELOPER_REFERENCE.md` §1–§6.
3. Run `python scripts/axonctl.py validate --network configs/network.yaml --agents configs/agents.yaml`.
4. Report any discrepancies between local state and on-chain reality.
5. Ask clarifying questions before executing any scale, deploy, or wallet command.
