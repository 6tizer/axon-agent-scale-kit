# 本机环境配置（Machine-Specific Paths）

> **这是模板文件，本身进 Git。**
> 每台协作机器 copy 一份并填入真实值：
> ```bash
> cp configs/runtime/local_env.template.md configs/runtime/local_env.md
> ```
> `local_env.md` 已在 `.gitignore` 中，**永远不进 Git**。

---

## SSH 访问生产服务器

| 项目 | 本机值（填入） |
|------|----------------|
| SSH 密钥路径 | `/path/to/your/QQClaw.pem` |
| 连接命令 | `ssh -i "/path/to/your/QQClaw.pem" ubuntu@43.165.195.71` |
| SCP 到服务器示例 | `scp -i "/path/to/your/QQClaw.pem" configs/runtime/network.runtime.yaml ubuntu@43.165.195.71:/home/ubuntu/axon-agent-scale/configs/runtime/` |

## 本机项目路径

| 项目 | 本机值（填入） |
|------|----------------|
| 本地 repo 根目录 | `/path/to/axon-agent-scale-kit` |
| Python 解释器 | `/path/to/.venv/bin/python` 或 `python3.11` |

---

## 服务器固定信息（所有机器相同，无需修改）

| 项目 | 值 |
|------|----|
| 服务器 IP | `43.165.195.71` (jakarta-node) |
| 用户名 | `ubuntu` |
| 服务器工作目录 | `/home/ubuntu/axon-agent-scale` |
| 服务器 state 文件 | `/home/ubuntu/axon-agent-scale/state/deploy_state.json` |
| Heartbeat service | `axon-heartbeat-daemon.service` |
