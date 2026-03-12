# Fiber Chaos Testing Tool

一个用于Fiber网络压力测试的命令行工具，模拟真实网络环境下的节点不稳定行为。

## 功能特性

- **批量账户创建**：自动生成N个Fiber账户并充值CKB
- **批量节点启动**：并行启动N个Fiber节点
- **自动通道建立**：所有节点与目标节点建立通道连接
- **混沌测试**：
  - 一半节点持续重启（模拟节点崩溃恢复）
  - 一半节点持续断开/重连（模拟网络不稳定）
- **实时监控**：监控网络状态、连接数、通道状态
- **统计报告**：测试完成后生成详细的统计摘要

## 使用方法

### 基本用法

```bash
# 运行10个节点，持续5分钟
python test_cases/fiber_chaos_test.py --count 10 --duration 300

# 简写形式
python test_cases/fiber_chaos_test.py -n 10 --duration 300
```

### 高级用法

```bash
# 20个节点，自定义重启和断开间隔
python test_cases/fiber_chaos_test.py \
  -n 20 \
  --restart-interval 5 \
  --disconnect-interval 3 \
  --duration 600

# 指定目标节点索引和资金配置
python test_cases/fiber_chaos_test.py \
  --count 10 \
  --target-index 0 \
  --ckb-amount 5000 \
  --funding-amount 20000000000 \
  --duration 300

# 启用详细日志
python test_cases/fiber_chaos_test.py -n 10 --verbose

# 无限运行（直到手动停止）
python test_cases/fiber_chaos_test.py -n 10
```

## 命令行参数

| 参数 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--count` | `-n` | 10 | Fiber节点数量（至少3个） |
| `--target-index` | | 0 | 目标节点的索引（作为中心节点） |
| `--duration` | | None | 测试持续时间（秒），不指定则无限运行 |
| `--restart-interval` | | 10.0 | 重启操作间隔（秒） |
| `--disconnect-interval` | | 5.0 | 断开/重连操作间隔（秒） |
| `--monitor-interval` | | 10.0 | 监控输出间隔（秒） |
| `--ckb-amount` | | 3000 | 每个账户的CKB金额 |
| `--funding-amount` | | 10000000000 | 通道资金（shannons） |
| `--base-rpc-port` | | 8500 | RPC起始端口 |
| `--base-p2p-port` | | 8600 | P2P起始端口 |
| `--verbose` | `-v` | False | 启用详细日志 |

## 测试架构

```
                    ┌───────────────┐
                    │  Target Node  │
                    │   (稳定运行)   │
                    └───────┬───────┘
                            │
           ┌────────────────┼────────────────┐
           │                │                │
    ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐
    │  Restart    │  │  Restart    │  │ Disconnect  │
    │   Group     │  │   Group     │  │   Group     │
    │  (N/2-1)    │  │  (N/2-1)    │  │   (N/2)     │
    └─────────────┘  └─────────────┘  └─────────────┘
         ↓重启            ↓重启          ↓断开/重连
```

## 输出示例

```
[2024-01-15 10:00:01] INFO - [Monitor] Peers: 9, Channels: 9, Active: 8, Restarts: 15, Disconnects: 42, Elapsed: 0:01:23
[2024-01-15 10:00:11] INFO - [Restart-1] Restarted (total: 16)
[2024-01-15 10:00:13] INFO - [Disconnect-5] Disconnected/reconnected (total: 43)

============================================================
FIBER CHAOS TEST SUMMARY
============================================================
Total Duration: 0:05:00
Total Nodes: 10
Restart Group Size: 4
Disconnect Group Size: 5
Total Restarts: 120
Total Disconnects: 300
Total Errors: 2
============================================================
```

## 日志文件

测试过程中会生成日志文件 `fiber_chaos_test.log`，包含详细的运行日志。

## 注意事项

1. **资源需求**：N个节点同时运行需要足够的系统资源（CPU、内存、端口）
2. **端口范围**：确保端口范围 `[base_port, base_port + count)` 可用
3. **CKB资金**：确保测试账户有足够的CKB资金
4. **清理**：测试完成后会自动清理所有节点和数据

## 故障排查

### 端口被占用
```bash
# 查看端口占用
lsof -i :8500-8510

# 杀掉占用进程
kill $(lsof -t -i :8500-8510)
```

### 节点启动失败
- 检查CKB节点是否正常启动
- 查看日志文件获取详细错误信息
- 使用 `--verbose` 启用详细日志

### 通道建立失败
- 确保账户有足够的CKB余额
- 检查目标节点是否正常运行
- 增加 `--funding-amount` 的值
