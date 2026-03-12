# Fiber Chaos Test - Distributed Cluster

分布式Fiber网络混沌测试系统，支持在多台机器上部署Fiber节点进行压力测试。

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      Master Node                            │
│                  (中心目标节点)                              │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│  │  CKB Node   │  │ Target Fiber │  │  API Server     │    │
│  │   :8114     │  │  :8227/8228  │  │    :5000        │    │
│  └─────────────┘  └──────────────┘  └─────────────────┘    │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
┌───────▼──────┐ ┌───▼────┐ ┌────▼──────┐
│  Worker-1    │ │Worker-2│ │ Worker-3  │
│  192.168.1.101│ │.102    │ │  .103     │
├──────────────┤ ├────────┤ ├───────────┤
│ ┌──────────┐ │ │ ┌────┐ │ │ ┌────────┐│
│ │ Fiber 1  │ │ │ │F1  │ │ │ │Fiber 1 ││
│ │ Fiber 2  │ │ │ │F2  │ │ │ │Fiber 2 ││
│ │ Fiber 3  │ │ │ │F3  │ │ │ │ ...    ││
│ │ Fiber 4  │ │ │ │F4  │ │ │ │Fiber M ││
│ │ Fiber 5  │ │ │ │F5  │ │ │ └────────┘│
│ └──────────┘ │ └──────┘ └─────────────┘
└──────────────┘
   (M个Fiber节点)
```

## 快速开始

### 1. 环境准备

在所有机器上安装依赖：

```bash
# 进入项目目录
cd fiber-py-integration-test

# 安装Python依赖
pip install flask requests pyyaml

# 确保框架代码可用
ls framework/basic_fiber.py  # 应该存在
```

### 2. 部署Master节点

在中心机器上执行：

```bash
# 启动Master节点
./chaos_cluster/deploy.sh --mode master

# 查看日志
tail -f logs/master_node.log

# 查看状态
./chaos_cluster/deploy.sh --mode status
```

Master启动后会显示目标节点信息，类似：
```
Target Peer ID: QmXxxxx...
Target Address: /ip4/192.168.1.100/tcp/8228/p2p/QmXxxxx...
```

### 3. 部署Worker节点

在每台工作机器上执行：

```bash
# 方式1: 使用部署脚本
./chaos_cluster/deploy.sh --mode worker --master 192.168.1.100

# 方式2: 直接运行（更灵活）
python3 chaos_cluster/worker_node.py \
  --master http://192.168.1.100:5000 \
  --worker-id worker-1 \
  --fiber-count 5
```

### 4. 启动测试

当所有Worker都注册并准备就绪后，Master会自动开始测试。你也可以手动控制：

```bash
# 查看当前状态
curl http://localhost:5000/api/status

# 手动开始测试
curl -X POST http://localhost:5000/api/start

# 停止测试
curl -X POST http://localhost:5000/api/stop
```

### 5. 停止测试

```bash
# 停止Master
./chaos_cluster/deploy.sh --mode stop

# 或者在Master机器上直接kill
kill $(cat logs/master_node.pid)
```

## 配置说明

编辑 `chaos_cluster/config.yaml`：

```yaml
# Master配置
master:
  host: "0.0.0.0"
  port: 5000

# 测试参数
test_params:
  ckb_per_account: 3000           # 每个账户CKB资金
  channel_funding: 10000000000    # Channel资金（100 CKB）
  restart_interval: 10            # 重启间隔（秒）
  disconnect_interval: 5          # 断开间隔（秒）

# Worker列表（仅用于参考）
workers:
  - id: "worker-1"
    host: "192.168.1.101"
    fiber_count: 5
```

## 工作流程

1. **初始化阶段**
   - Master启动CKB节点和目标Fiber节点
   - Worker连接Master获取目标节点信息
   - Worker创建账户（需要资金）
   - Worker启动本地Fiber节点

2. **连接阶段**
   - 所有Worker的Fiber节点连接到目标节点
   - 自动开启Channel
   - Worker通知Master准备就绪

3. **混沌测试阶段**
   - Master发出开始信号
   - 每个Fiber节点同时执行：
     - 停止 → 等待 → 启动 → 重连（模拟崩溃恢复）
     - 断开 → 等待 → 重连（模拟网络不稳定）
   - Worker定期上报统计信息

4. **监控阶段**
   - Master实时监控：
     - 连接节点数
     - Channel数量
     - 重启/断开次数
     - 错误日志

## API接口

### Master API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/target_info` | GET | 获取目标节点信息 |
| `/api/register` | POST | Worker注册 |
| `/api/ready` | POST | Worker准备就绪通知 |
| `/api/stats` | POST | 上报统计信息 |
| `/api/start` | POST | 开始测试 |
| `/api/stop` | POST | 停止测试 |
| `/api/status` | GET | 获取整体状态 |

### 示例请求

```bash
# 获取目标信息
curl http://master:5000/api/target_info

# Worker注册
curl -X POST http://master:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{"worker_id":"worker-1","worker_ip":"192.168.1.101","fiber_count":5}'

# 上报统计
curl -X POST http://master:5000/api/stats \
  -H "Content-Type: application/json" \
  -d '{
    "worker_id": "worker-1",
    "stats": {
      "restart_count": 10,
      "disconnect_count": 20,
      "errors": []
    }
  }'
```

## 大规模部署脚本

使用SSH在多台机器上批量部署：

```bash
# deploy_cluster.sh
MASTER_IP="192.168.1.100"
WORKERS=("192.168.1.101" "192.168.1.102" "192.168.1.103")

# 部署Master
ssh ubuntu@$MASTER_IP "cd /opt/fiber-test && ./chaos_cluster/deploy.sh --mode master"

# 部署Workers
for i in "${!WORKERS[@]}"; do
  WORKER_IP=${WORKERS[$i]}
  WORKER_ID="worker-$((i+1))"
  echo "Deploying $WORKER_ID on $WORKER_IP..."
  
  ssh ubuntu@$WORKER_IP \
    "cd /opt/fiber-test && python3 chaos_cluster/worker_node.py \
      --master http://$MASTER_IP:5000 \
      --worker-id $WORKER_ID \
      --fiber-count 5 \
      > logs/worker.log 2>&1 &"
done

echo "Deployment complete!"
```

## 监控和日志

### 实时监控

```bash
# Master监控
curl -s http://master:5000/api/status | jq

# 或者使用watch
watch -n 2 'curl -s http://master:5000/api/status | jq .stats'
```

### 日志文件

- `logs/master_node.log` - Master节点日志
- `logs/worker_node.log` - Worker节点日志
- `fiber_chaos_test.log` - 测试统计日志

### 输出示例

```
[2024-01-15 10:00:01] INFO - [Monitor] Peers: 15, Channels: 15, Active: 14
[2024-01-15 10:00:11] INFO - [Restart-worker-1-Fiber0] Restarted (total: 156)
[2024-01-15 10:00:13] INFO - [Disconnect-worker-2-Fiber3] Disconnected (total: 342)

============================================================
FIBER DISTRIBUTED CHAOS TEST SUMMARY
============================================================
Total Duration: 0:30:00
Total Workers: 3
Total Fibers: 15
Connected Peers: 15
Total Channels: 15
Total Restarts: 1500
Total Disconnects: 3200
============================================================
```

## 故障排查

### Worker无法连接Master

```bash
# 检查网络连通性
ping master-ip

# 检查Master API
curl http://master-ip:5000/api/target_info

# 检查防火墙
sudo ufw allow 5000/tcp
```

### Fiber节点启动失败

```bash
# 检查端口占用
lsof -i :8500-8510

# 检查CKB节点连接
curl http://master-ip:8114 \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"get_tip_block_number","params":[],"id":1}'
```

### Channel建立失败

- 确保账户有足够的CKB资金
- 检查目标节点是否正常运行
- 查看Fiber节点日志：`tail -f chaos_worker/*/fiber_*/node.log`

## 性能考虑

### 推荐配置

| 规模 | Worker机器数 | 每机器Fiber数 | 总Fiber数 | 网络带宽 |
|------|-------------|--------------|----------|----------|
| 小型 | 2-3 | 5 | 10-15 | 100Mbps |
| 中型 | 5-10 | 10 | 50-100 | 1Gbps |
| 大型 | 20+ | 20+ | 400+ | 10Gbps |

### 资源需求

每Fiber节点大约需要：
- CPU: 0.5-1 核
- 内存: 512MB-1GB
- 磁盘: 1GB
- 网络: 持续低频通信

## 扩展开发

### 添加自定义测试逻辑

编辑 `worker_node.py` 中的 `chaos_worker` 方法：

```python
def chaos_worker(self, fiber: Fiber, fiber_index: int):
    while not self.stop_event.is_set():
        # 添加你的自定义逻辑
        # 例如：随机支付测试
        if random.random() < 0.1:
            self.send_random_payment(fiber)
        
        # 原有的重启和断开逻辑
        ...
```

### 添加自定义监控指标

编辑 `master_node.py` 中的 `get_status` 方法：

```python
def get_status(self) -> dict:
    status = {
        # 原有指标
        ...
        # 自定义指标
        "custom_metric": self.calculate_custom_metric()
    }
    return status
```
