# 腾讯云 Axon 验证节点整理计划

## 当前状况

| 项目      | 状态            |
| ------- | ------------- |
| 本地工作区   | ✅ 已整理完成       |
| 服务器登录信息 | ✅ 你有          |
| 新节点私钥密码 | ✅ 你有备份        |
| 服务器现状   | ❌ 未知（旧+新节点混乱） |

***

## 阶段一：SSH连接并诊断服务器现状

### 1.1 连接服务器

#### 1.1.1 连接服务器

```bash
ssh ubuntu@43.165.195.71
```

#### 1.1.2 把服务器连接信息填入README.md

**更新文档：** `README.md` → 服务器IP

***

### 1.2 诊断命令（只读操作）

#### 1.2.1 查看运行中的进程

```bash
ps aux | grep axond
```

**更新文档：** `README.md` → 更新/新建 “axond进程状态”

#### 1.2.2 查看Docker容器

```bash
docker ps -a | grep axon
```

**更新文档：** `README.md` → 更新/新建 “docker容器状态”

#### 1.2.3 查看/opt目录

```bash
ls -la /opt/
```

**更新文档：** `README.md` → 更新/新建 “节点目录”

#### 1.2.4 查看节点配置目录

```bash
ls -la ~/.axon/config/
```

**更新文档：** `README.md` → 更新/新建 “私钥文件路径”

***

### 1.3 诊断输出

#### 1.3.1 查询节点状态

```bash
curl -s http://localhost:26657/status | jq .
```

**更新文档：** `README.md` → 更新/新建“chain\_id、同步状态、validator地址”

#### 1.3.2 查询验证者列表

```bash
curl -s http://localhost:26657/validators | jq .
```

**更新文档：** `README.md` → 更新/新建“ 验证者数量和地址”

***

### 1.4 诊断结论

#### 1.4.1 判断新旧节点状态

根据1.2-1.3结果，判断：

- 是否有两个节点在运行？
- 哪个是旧节点，哪个是新节点？
  **更新文档：** `docs/custom/NODES_STATUS.md` → 添加诊断结论

#### 1.4.2 把诊断结果填入README.md

**更新文档：** `README.md` → 更新"待确认信息"表格（填入已核实的信息）

***

## 阶段二：建立标准目录结构

### 2.1 创建/opt/axon目录

#### 2.1.1 创建目录结构

```bash
sudo mkdir -p /opt/axon/{keys,config,scripts,logs,backups}
```

**更新文档：** `README.md` → 更新/新建“ 目录结构”

#### 2.1.2 设置keys目录权限

```bash
sudo chmod 700 /opt/axon/keys
```

**更新文档：** `README.md` → 更新/新建“权限设置”

***

### 2.2 创建运维脚本

#### 2.2.1 创建start.sh

```bash
vi /opt/axon/scripts/start.sh
chmod +x /opt/axon/scripts/start.sh
```

**更新文档：** `scripts/deploy/start.sh` → 同步到本地

#### 2.2.2 创建stop.sh

```bash
vi /opt/axon/scripts/stop.sh
chmod +x /opt/axon/scripts/stop.sh
```

**更新文档：** `scripts/deploy/stop.sh` → 同步到本地

#### 2.2.3 创建status.sh

```bash
vi /opt/axon/scripts/status.sh
chmod +x /opt/axon/scripts/status.sh
```

**更新文档：** `scripts/deploy/status.sh` → 同步到本地

***

## 阶段三：部署正确的私钥

### 3.1 备份现有配置

#### 3.1.1 备份genesis.json

```bash
cp ~/.axon/config/genesis.json /opt/axon/config/genesis.json.bak
```

**更新文档：** `docs/custom/SERVER_DEPLOY.md` → genesis备份位置

#### 3.1.2 备份现有私钥

```bash
mkdir -p /opt/axon-backup/keys_old
cp ~/.axon/config/priv_validator_key.json /opt/axon-backup/keys_old/
```

**更新文档：** `docs/custom/SERVER_DEPLOY.md` → 旧私钥备份位置

***

### 3.2 部署正确私钥

#### 3.2.1 复制genesis.json到标准位置

```bash
cp /opt/axon/config/genesis.json.bak /opt/axon/config/genesis.json
```

**更新文档：** `docs/custom/SERVER_DEPLOY.md` → genesis路径

#### 3.2.2 部署priv\_validator\_key.json

```bash
vi /opt/axon/keys/priv_validator_key.json
# 放入你备份的正确私钥内容
```

**更新文档：** `validator-keys/CURRENT/README.md` → 核对私钥内容

#### 3.2.3 部署node\_key.json

```bash
vi /opt/axon/keys/node_key.json
# 放入正确内容
```

**更新文档：** `validator-keys/CURRENT/README.md` → 更新node\_key信息

#### 3.2.4 设置私钥文件权限

```bash
chmod 600 /opt/axon/keys/*.json
```

**更新文档：** `docs/custom/axon-server-structure.md` → 权限600

***

## 阶段四：停止混乱的旧/新节点

### 4.1 记录停止前状态

#### 4.1.1 再次确认运行状态

```bash
ps aux | grep axond
docker ps -a | grep axon
```

**更新文档：** `docs/custom/NODES_STATUS.md` → "停止前"状态快照

***

### 4.2 停止节点

#### 4.2.1 停止axond进程

```bash
pkill axond
```

**更新文档：** `docs/custom/NODES_STATUS.md` → axond已停止

#### 4.2.2 停止并删除Docker容器

```bash
docker stop $(docker ps -aq --filter name=axon)
docker rm $(docker ps -aq --filter name=axon)
```

**更新文档：** `docs/custom/NODES_STATUS.md` → docker容器已删除

#### 4.2.3 确认所有节点已停止

```bash
ps aux | grep axond
docker ps -a | grep axon
```

**更新文档：** `docs/custom/NODES_STATUS.md` → 确认无进程运行

***

### 4.3 记录旧节点信息

#### 4.3.1 记录旧节点数据位置

```bash
ls -la /opt/
```

**更新文档：** `validator-keys/ARCHIVED/README.md` → 旧节点目录信息

#### 4.3.2 更新SERVER\_DEPLOY.md

**更新文档：** `docs/custom/SERVER_DEPLOY.md` → 添加"旧节点处理"章节

***

## 阶段五：使用正确私钥启动标准节点

### 5.1 配置软链接

#### 5.1.1 创建priv\_validator\_key.json软链接

```bash
ln -sf /opt/axon/keys/priv_validator_key.json ~/.axon/config/priv_validator_key.json
```

**更新文档：** `docs/custom/axon-server-structure.md` → 软链接配置

#### 5.1.2 创建genesis.json软链接

```bash
ln -sf /opt/axon/config/genesis.json ~/.axon/config/genesis.json
```

**更新文档：** `docs/custom/axon-server-structure.md` → 软链接配置

***

### 5.2 启动节点

#### 5.2.1 启动axond

```bash
axond start
```

**更新文档：** `docs/custom/SERVER_DEPLOY.md` → 运行方式

#### 5.2.2 等待启动并验证

```bash
sleep 10
curl -s http://localhost:26657/status
```

**更新文档：** `docs/custom/NODES_STATUS.md` → 节点已启动

***

### 5.3 验证运行状态

#### 5.3.1 检查同步状态

```bash
curl -s http://localhost:26657/status | jq .result.sync_info.catching_up
```

**更新文档：** `docs/custom/NODES_STATUS.md` → 同步状态

#### 5.3.2 检查验证者状态

```bash
curl -s http://localhost:26657/validators | jq .
```

**更新文档：** `validator-keys/CURRENT/README.md` → 验证者地址和voting\_power

#### 5.3.3 更新最终状态

**更新文档：** `README.md` → 移除"⚠️需核实"标记

***

## 阶段六：设置自动备份

### 6.1 创建备份脚本

#### 6.1.1 创建backup.sh

```bash
vi /opt/axon/scripts/backup.sh
chmod +x /opt/axon/scripts/backup.sh
```

**更新文档：** `scripts/deploy/backup.sh` → 同步到本地

#### 6.1.2 测试备份脚本

```bash
/opt/axon/scripts/backup.sh
ls -la /opt/axon/backups/
```

**更新文档：** `docs/custom/OPERATIONS.md` → 备份操作章节

***

### 6.2 设置定时任务

#### 6.2.1 编辑crontab

```bash
crontab -e
# 添加: 0 3 * * * /opt/axon/scripts/backup.sh >> /opt/axon/logs/backup.log 2>&1
```

**更新文档：** `docs/custom/OPERATIONS.md` → crontab配置

***

## 阶段七：最终整理

### 7.1 整理SERVER\_DEPLOY.md

**更新文档：** `docs/custom/SERVER_DEPLOY.md` → 移除所有"⚠️需核实"标记

### 7.2 整理validator-keys

**更新文档：** `validator-keys/CURRENT/README.md` → 完整准确的验证者信息

### 7.3 创建OPERATIONS.md

**更新文档：** 创建 `docs/custom/OPERATIONS.md` → 日常检查、备份恢复、紧急联系

### 7.4 最终检查

**更新文档：** 确认所有文档已完成同步

***

## 预期结果

1. ✅ 服务器只有一个标准节点运行
2. ✅ 使用你备份的正确私钥
3. ✅ 建立标准目录结构和备份机制
4. ✅ 本地工作区与服务器状态完全同步

