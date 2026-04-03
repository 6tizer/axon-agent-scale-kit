# 协作者工作流（GitHub Fork + PR）

## 角色定义

| 角色 | 职责 | 机器 |
|---|---|---|
| 6tizer（Owner） | 最终验收人，所有 PR 必须由其审核合并 | Mac mini + Server |
| 协作者（Agent） | Fork 仓库，开发功能，通过 PR 合入 | 本地开发机 |
| GitHub | 协作中枢，保护 main，托管 PR | — |
| Server | 最终运行环境，只跑 main 分支 | 生产服务器 |

## 操作分层（三层模型）

所有对代码或服务器的操作，按影响范围分为三层，每层有不同的合法路径：

| 层级 | 操作类型 | 路径 | 适用场景 |
|------|---------|------|---------|
| **只读层** | 查看日志、状态、`deploy_state.json` | 直接 SSH，不改任何文件 | 问题排查、链上状态核查 |
| **配置层** | 修改 `configs/runtime/*.yaml`（gitignored） | 直接 SCP 到服务器，不走 GitHub | 调整 RPC URL、keyring 路径等机器特定配置 |
| **代码层** | 修改 `scripts/`、`configs/`（非 runtime）、文档 | 必须走 GitHub PR → merge → server git pull | 所有逻辑变更 |

> **配置层说明**：`configs/runtime/*.yaml` 本身在 `.gitignore` 中，不受版本控制管理。  
> 直接 SCP 是合法且预期的操作，不违反下方"只跑 main 分支"红线——该红线管的是**代码**，不是 runtime configs。

---

## 红线规则

- **Server 代码永远只跑 main 分支**，不直接跑非 main 代码，不在服务器上做临时开发。
- **`configs/runtime/` 是例外**：这些文件 gitignored，各机器/服务器维护自己的版本，可直接 SCP，无需走 GitHub。
- **协作者不能直接推 origin**，所有代码必须通过 PR 合入。
- **禁止跳过 PR 直接 merge** 到 main（GitHub 分支保护规则强制执行）。

---

## 仓库初始化（协作者一次性操作）

### Fork 仓库

在 GitHub 上，将 `6tizer/axon-agent-scale-kit` Fork 到协作者账号。

### 配置 remote

```bash
# 克隆协作者的 Fork
git clone git@github.com:<your-github>/axon-agent-scale-kit.git
cd axon-agent-scale-kit

# 添加上游仓库（6tizer 原仓库）
git remote add upstream git@github.com:6tizer/axon-agent-scale-kit.git

# 确认配置
git remote -v
# origin    git@github.com:<your-github>/axon-agent-scale-kit.git (fetch)
# origin    git@github.com:<your-github>/axon-agent-scale-kit.git (push)
# upstream  git@github.com:6tizer/axon-agent-scale-kit.git (fetch)
# upstream  git@github.com:6tizer/axon-agent-scale-kit.git (push)
```

---

## 日常开发流程

### 步骤 1：6tizer 推送新功能到 main

```bash
# 6tizer Mac mini
git checkout main
git pull origin main
# ... 开发新功能 ...
git add .
git commit -m "feat: 完成新功能A"
git push origin main
```

### 步骤 2：协作者同步 6tizer 的最新代码

```bash
# 协作者本地
git fetch upstream
git checkout main
git merge upstream/main
```

> 协作者的 main 分支永远保持和 6tizer main 同步，不在 main 上直接开发。

### 步骤 3：协作者从最新 main 创建功能分支

```bash
git checkout -b feature/my-new-feature
# ... 开发新功能 ...
git add .
git commit -m "feat: 新功能描述"
```

### 步骤 4：协作者推送分支到自己的 Fork

```bash
git push origin feature/my-new-feature
```

### 步骤 5：协作者在 GitHub 提 Pull Request

```
我的 Fork 仓库 → Compare & pull request
  base:  6tizer/main   ← 合入目标
  compare: feature/my-new-feature
```

### 步骤 6：6tizer Code Review

6tizer 在 GitHub 上收到 PR 通知，Review 代码：

- **通过** → 点击 Merge，PR 合入 main
- **需要修改** → 在 PR 下评论，协作者继续修改并 push

> 协作者 push 新 commit 后，PR 会自动更新，无需重新提 PR。

### 步骤 7：Server 同步最新 main 并部署

```bash
# 服务器
git fetch origin
git checkout main
git pull origin main
# ... 部署脚本重启服务 ...
```

### 步骤 8：6tizer 在 Server 验收

```bash
python3 scripts/axonctl.py lifecycle-report \
  --state-file state/deploy_state.json \
  --network configs/network.yaml
```

---

## 分支保护规则（GitHub 配置项）

在 GitHub 仓库 **Settings → Branches** 中配置：

```
main 分支保护规则：
  ☑ Require pull request reviews before merging（至少 1 人 Review）
  ☑ Require status checks to pass before merging（CI 通过）
  ☑ Include administrators（6tizer 也必须走 PR）
  ☑ Do not allow force pushes
```

---

## Server 问题处理流程

### 情况 A：Bug 在协作者的代码里

```
Server 验收发现 Bug
        ↓
6tizer 在 GitHub PR 下评论标注问题
        ↓
协作者本地修复 → commit → push
        ↓
PR 自动更新
        ↓
6tizer 再次 Review → 通过 → Merge
        ↓
Server git pull main
        ↓
再次验收
```

### 情况 B：紧急 Bug，需要走 hotfix

```
场景：PR 流程太慢，Server 必须立即修复
        ↓
6tizer 在本地从 main 创建 hotfix 分支
        ↓
6tizer 修复 → push → 提 PR → 自己 Review → Merge
        ↓
Server 立即 git pull main
        ↓
问题修复后，告知协作者
        ↓
协作者 rebase 自己的分支（见下方 rebase 流程）
```

### 情况 C：协作者分支需要 rebase 最新的 main

```bash
# 协作者本地
git fetch upstream
git checkout feature/my-feature
git rebase upstream/main

# 如果产生冲突，Git 会报告冲突文件
# 打开冲突文件，手动决定保留哪个版本
# 解决完冲突后：
git add .
git rebase --continue

# 强制推送更新（rebase 改写了 commit 历史）
git push --force-with-lease origin feature/my-feature
```

> 注意：rebase 后必须用 `--force-with-lease`，不能用 `--force`，否则可能覆盖他人的 push。

---

## 冲突解决流程

当 rebase 产生冲突时，按以下步骤处理：

### 第 1 步：Git 报告冲突

```
CONFLICT (content): Merge conflict in scripts/axonctl.py
Automatic merge failed; fix conflicts and then commit the result.
```

### 第 2 步：查看冲突文件

Git 在冲突处做了标记：

```python
<<<<<<< HEAD（6tizer 的版本）
    return "hello, world!"
=======
    return "hello, axon!"   # 协作者的版本
>>>>>>> feature/my-feature
```

### 第 3 步：手动决定保留哪个

- 保留 6tizer 的：删掉标记，只留一行
- 保留协作者的：删掉标记，只留一行
- 两边合并：自己写一个新版本

### 第 4 步：标记已解决

```bash
git add scripts/axonctl.py
git rebase --continue
```

### 放弃 rebase（如果搞砸了）

```bash
git rebase --abort   # 回到 rebase 之前的状态
```

---

## 常用 Git 命令速查

### 协作者同步最新代码

```bash
git fetch upstream
git checkout main
git merge upstream/main
```

### 创建功能分支

```bash
git checkout -b feature/my-new-feature
```

### 推送分支

```bash
git push origin feature/my-new-feature
```

### rebase 最新 main

```bash
git fetch upstream
git checkout feature/my-feature
git rebase upstream/main
```

### 强制推送（rebase 后使用）

```bash
git push --force-with-lease origin feature/my-feature
```

### 查看当前状态

```bash
git status
git remote -v
git branch -a
```

---

## 全流程图

```
6tizer Mac mini          协作者                    GitHub              Server
      │                      │                         │                    │
      │  1. 开发完成 push    │                         │                    │
      │─────────────────────>│                         │                    │
      │                      │  2. fetch upstream      │                    │
      │                      │  merge upstream/main     │                    │
      │                      │────────────────────────>│                    │
      │                      │                         │                    │
      │                      │  3. 创建 feat 分支       │                    │
      │                      │  开发 + commit          │                    │
      │                      │                         │                    │
      │                      │  4. push origin feat/   │                    │
      │                      │────────────────────────>│                    │
      │                      │                         │                    │
      │                      │  5. 提 PR（Fork→main）  │                    │
      │                      │────────────────────────>│                    │
      │                      │                         │                    │
      │  收到 PR 通知        │                         │                    │
      │  Code Review        │                         │                    │
      │<─────────────────────────────────────────────────────────────────>│
      │                      │                         │                    │
      │  6. Review 通过      │                         │                    │
      │  Merge PR           │                         │                    │
      │──────────────────────────────────────────────────────────────────────────>│
      │                      │                         │                    │
      │                      │                         │  7. git pull main  │
      │                      │                         │<───────────────────│
      │                      │                         │                    │
      │  8. Server 验收      │                         │                    │
      │<─────────────────────────────────────────────────────────────────────────│
      │                      │                         │                    │
      │  9. 验收通过          │  10. 同步最新 main       │                    │
      │<─────────────────────│────────────────────────>│                    │
```

---

## 排障协议（Debug Protocol）

### 排障前：必须先核查代码同步状态

**本地与服务器跑的不是同一份代码**是排查 bug 时最常见的隐性陷阱。在任何排查之前，先做一步：

```bash
# Step 1：本地
git log -1 --format='%H %s'

# Step 2：SSH 进服务器
ssh -i "<ssh_key_from_local_env.md>" ubuntu@43.165.195.71
cd /home/ubuntu/axon-agent-scale
git log -1 --format='%H %s'
```

| 结果 | 行动 |
|------|------|
| hash 一致 | 继续排查，本地代码即为服务器代码 |
| hash 不一致 | 先在服务器 `git pull origin main` + 重启服务，再排查 |

### 按 bug 类型选择排查位置

| Bug 类型 | 排查位置 | 原因 |
|---------|---------|------|
| 逻辑错误、计算错误 | **本地 IDE** | 工具最全，代码同步后本地即是权威 |
| 运行时状态异常（agent 心跳/challenge 失败） | **服务器 `state/deploy_state.json`** | state 文件 gitignored，只存在于服务器 |
| 服务崩溃、启动失败 | **服务器 `journalctl`** | `journalctl -u axon-heartbeat-daemon -n 100 --no-pager` |
| 环境/依赖/网络问题 | **服务器直连** | 本地环境无法完全复现 |
| `axond` keyring / Cosmos 交易失败 | **服务器直连** | keyring 数据只在服务器上 |

### 常用服务器排查命令（只读）

```bash
# 服务状态
sudo systemctl status axon-heartbeat-daemon.service

# 最近 100 行日志
journalctl -u axon-heartbeat-daemon -n 100 --no-pager

# 查看 state（只读）
cat /home/ubuntu/axon-agent-scale/state/deploy_state.json | python3 -m json.tool | head -80

# 当前代码版本
git -C /home/ubuntu/axon-agent-scale log -1 --format='%H %s %ci'

# Docker 容器状态
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.RunningFor}}"
```

> **只读原则**：排查过程中不修改服务器上的代码文件。配置调整走配置层（SCP），逻辑修复走代码层（GitHub PR）。

