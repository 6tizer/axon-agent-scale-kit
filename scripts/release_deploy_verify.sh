#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/release_deploy_verify.sh [options]

Options:
  --remote-host <host>       Remote host (default: 43.165.195.71)
  --remote-user <user>       Remote user (default: ubuntu)
  --ssh-key <path>           SSH private key path
                             (default: ${HOME}/Downloads/QQClaw.pem)
  --remote-dir <path>         Remote workdir (default: /home/ubuntu/axon-agent-scale)
  --service <name>           systemd service to restart/verify
                             (default: axon-heartbeat-daemon.service)
  --skip-tests               Skip local unittest before push
  --allow-dirty              Allow dirty working tree
  --dry-run                  Print actions without mutating remote/local state
  -h, --help                 Show this help

Examples:
  scripts/release_deploy_verify.sh
  scripts/release_deploy_verify.sh --dry-run --allow-dirty --skip-tests
EOF
}

log() {
  printf '[release] %s\n' "$*"
}

die() {
  printf '[release][error] %s\n' "$*" >&2
  exit 1
}

REMOTE_HOST="43.165.195.71"
REMOTE_USER="ubuntu"
SSH_KEY="${HOME}/Downloads/QQClaw.pem"
REMOTE_DIR="/home/ubuntu/axon-agent-scale"
SERVICE_NAME="axon-heartbeat-daemon.service"
SKIP_TESTS=0
ALLOW_DIRTY=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remote-host)
      [[ $# -ge 2 ]] || die "missing value for --remote-host"
      REMOTE_HOST="$2"
      shift 2
      ;;
    --remote-user)
      [[ $# -ge 2 ]] || die "missing value for --remote-user"
      REMOTE_USER="$2"
      shift 2
      ;;
    --ssh-key)
      [[ $# -ge 2 ]] || die "missing value for --ssh-key"
      SSH_KEY="$2"
      shift 2
      ;;
    --remote-dir)
      [[ $# -ge 2 ]] || die "missing value for --remote-dir"
      REMOTE_DIR="$2"
      shift 2
      ;;
    --service)
      [[ $# -ge 2 ]] || die "missing value for --service"
      SERVICE_NAME="$2"
      shift 2
      ;;
    --skip-tests)
      SKIP_TESTS=1
      shift
      ;;
    --allow-dirty)
      ALLOW_DIRTY=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

command -v git >/dev/null 2>&1 || die "git not found"
command -v ssh >/dev/null 2>&1 || die "ssh not found"
command -v python3 >/dev/null 2>&1 || die "python3 not found"

[[ -f "$SSH_KEY" ]] || die "ssh key not found: $SSH_KEY"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "must run inside git repository"
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if pgrep -f "axonctl.py heartbeat-daemon" >/dev/null 2>&1; then
  die "local heartbeat-daemon appears to be running; stop local daemon before release"
fi

if [[ "$ALLOW_DIRTY" -ne 1 ]]; then
  if ! git diff --quiet || ! git diff --cached --quiet || [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
    die "working tree is dirty; commit/stash changes or pass --allow-dirty"
  fi
fi

LOCAL_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
LOCAL_COMMIT="$(git rev-parse HEAD)"
LOCAL_SHORT="$(git rev-parse --short HEAD)"

log "local branch: $LOCAL_BRANCH"
log "local commit: $LOCAL_COMMIT"

if [[ "$LOCAL_BRANCH" == "main" ]]; then
  die "pushing directly to main is forbidden; all changes must go through a PR reviewed by 6tizer"
fi

log "pushing HEAD to origin/$LOCAL_BRANCH"

if [[ "$SKIP_TESTS" -ne 1 ]]; then
  log "running local regression: python3 -m unittest tests.test_axonctl -q"
  python3 -m unittest tests.test_axonctl -q
else
  log "skip tests enabled"
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  log "DRY RUN: would push HEAD to origin/$LOCAL_BRANCH"
else
  log "pushing HEAD to origin/$LOCAL_BRANCH"
  git push origin HEAD
fi

remote_head="$(git ls-remote --heads origin "$LOCAL_BRANCH" | awk '{print $1}')"
if [[ "$remote_head" != "$LOCAL_COMMIT" ]]; then
  die "origin/$LOCAL_BRANCH ($remote_head) does not match local commit ($LOCAL_COMMIT)"
fi

SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new -i "$SSH_KEY")
SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  log "DRY RUN: would ensure remote directory: $REMOTE_DIR"
  log "DRY RUN: would deploy commit archive (scripts, configs, README.md, requirements.txt)"
  log "DRY RUN: would write $REMOTE_DIR/.release_meta.json"
  log "DRY RUN: would restart service $SERVICE_NAME and run lifecycle verification"
  exit 0
fi

log "ensuring remote directories"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "mkdir -p '$REMOTE_DIR' '$REMOTE_DIR/scripts' '$REMOTE_DIR/configs'"

# ── axond 安装 ─────────────────────────────────────────────────────────────────
log "installing axond (Cosmos SDK CLI for challenge commit/reveal)"
AXOND_VERSION="${AXOND_VERSION:-v1.0.0}"
AXOND_INSTALL_SCRIPT="
  set -e
  if command -v axond >/dev/null 2>&1; then
    echo '[axond] already installed:'; axond version
  else
    echo '[axond] downloading release ${AXOND_VERSION}...'
    # Axonchain 的 axond 下载 URL 格式（需确认官方实际地址）
    AXOND_URL=\"\"
    # 备选：容器内已有 axond，检查路径
    if docker exec axon-node which axond >/dev/null 2>&1; then
      echo '[axond] found in axon-node container'
    else
      echo '[axond] will be resolved at runtime via AXOND_PATH env var'
    fi
  fi
"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "$AXOND_INSTALL_SCRIPT"

# ── axond 密钥导入 ──────────────────────────────────────────────────────────────
log "importing agent keys into axond keyring"
AXOND_KEY_IMPORT_SCRIPT="
  set -e
  KEYRING_DIR=\"\${HOME}/.axond\"
  mkdir -p \"\${KEYRING_DIR}\"
  chmod 700 \"\${KEYRING_DIR}\"
  STATE_FILE='${REMOTE_DIR}/state/deploy_state.json'
  if [[ ! -f \"\${STATE_FILE}\" ]]; then
    echo '[axond-key-import] state file not found: '\${STATE_FILE}
    exit 0
  fi
  # 从 deploy_state.json 读取 agent wallets，导入到 axond keyring
  # 注意：axond keys import <name> <hex_privkey> --keyring-backend file
  echo '[axond-key-import] reading wallets from state...'
  # shellcheck disable=SC2016
  python3 -c \"
import json, subprocess, sys
with open('${REMOTE_DIR}/state/deploy_state.json') as f:
    state = json.load(f)
for key_id, wallet in state.get('wallets', {}).items():
    if wallet.get('role') != 'agent':
        continue
    label = wallet.get('label', '')
    if not label.startswith('agent:'):
        continue
    agent_name = label.split(':', 1)[1]
    privkey = wallet.get('private_key', '')
    if not privkey:
        continue
    privkey_hex = privkey[2:] if privkey.startswith('0x') else privkey
    result = subprocess.run(
        ['axond', 'keys', 'import', agent_name, privkey_hex,
         '--keyring-backend', 'file',
         '--keyring-dir', '${HOME}/.axond'],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f'[axond-key-import] imported: {agent_name}')
    else:
        # 密钥可能已存在，尝试获取公钥确认
        check = subprocess.run(
            ['axond', 'keys', 'get', agent_name,
             '--keyring-dir', '${HOME}/.axond'],
            capture_output=True, text=True
        )
        if check.returncode == 0:
            print(f'[axond-key-import] already exists: {agent_name}')
        else:
            print(f'[axond-key-import] FAILED {agent_name}: {result.stderr.strip()}')
\" 2>&1 | head -20
  chmod 700 \"\${KEYRING_DIR}\"
  echo '[axond-key-import] done'
"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "$AXOND_KEY_IMPORT_SCRIPT"

log "deploying tracked files from commit $LOCAL_SHORT"
git archive --format=tar "$LOCAL_COMMIT" scripts configs README.md requirements.txt \
  | ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "tar -xf - -C '$REMOTE_DIR'"

# ── axond keyring 目录初始化 ─────────────────────────────────────────────────
# 在 systemd service 运行前设置密钥环目录权限（bootstrap 阶段，而非 runtime）
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" \
  "mkdir -p '${HOME}/.axond' && chmod 700 '${HOME}/.axond' && echo 'keyring dir ready at ${HOME}/.axond'"

# ── challenge-daemon 部署 ──────────────────────────────────────────────────────
log "deploying axon-challenge-daemon.service"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" \
  "sudo cp '$REMOTE_DIR/scripts/systemd/axon-challenge-daemon.service' \
          '/etc/systemd/system/axon-challenge-daemon.service' && \
   sudo systemctl daemon-reload && \
   sudo systemctl enable axon-challenge-daemon && \
   sudo systemctl restart axon-challenge-daemon && \
   echo '[release] axon-challenge-daemon deployed and started'"

log "challenge-daemon status"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "systemctl is-active axon-challenge-daemon"

deployed_at="$(date '+%Y-%m-%d %H:%M:%S %Z')"
cat <<EOF | ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "cat > '$REMOTE_DIR/.release_meta.json'"
{
  "commit": "$LOCAL_COMMIT",
  "short_commit": "$LOCAL_SHORT",
  "deployed_at": "$deployed_at",
  "deployed_by": "$(whoami)",
  "source_repo": "$(git remote get-url origin)"
}
EOF

log "restarting service: $SERVICE_NAME"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "sudo systemctl restart '$SERVICE_NAME'"

log "service status"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "systemctl is-active '$SERVICE_NAME'"

log "docker status snapshot"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "docker ps --format '{{.Names}}|{{.Status}}|{{.Image}}' | sort"

log "lifecycle verification"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" \
  "python3 '$REMOTE_DIR/scripts/axonctl.py' lifecycle-report --state-file '$REMOTE_DIR/state/deploy_state.json' --network '$REMOTE_DIR/configs/network.yaml'"

log "release flow completed for commit $LOCAL_SHORT"
