#!/bin/bash
# 分布式部署示例脚本 - 3台机器，每台5个Fiber节点

# 配置
MASTER_IP="192.168.1.100"
WORKER_IPS=("192.168.1.101" "192.168.1.102" "192.168.1.103")
FIBERS_PER_WORKER=5
PROJECT_DIR="/opt/fiber-py-integration-test"

echo "=========================================="
echo "Fiber Chaos Test - Distributed Deployment"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Master: $MASTER_IP"
echo "  Workers: ${#WORKER_IPS[@]} machines"
echo "  Fibers per worker: $FIBERS_PER_WORKER"
echo "  Total fibers: $((${#WORKER_IPS[@]} * $FIBERS_PER_WORKER))"
echo ""

# 步骤1: 部署Master
echo "[Step 1] Deploying Master Node on $MASTER_IP..."
ssh ubuntu@$MASTER_IP "
    cd $PROJECT_DIR
    source venv/bin/activate
    nohup python chaos_cluster/master_node.py \\
        --config chaos_cluster/config.yaml \\
        --port 5000 \\
        > logs/master.log 2>&1 &
echo "  Master PID: \$(cat logs/master.pid)"
"

if [ $? -ne 0 ]; then
    echo "Failed to deploy master"
    exit 1
fi

echo "  ✓ Master deployed"
echo ""

# 等待Master启动
sleep 5

# 步骤2: 部署Workers
echo "[Step 2] Deploying Worker Nodes..."
for i in "${!WORKER_IPS[@]}"; do
    WORKER_IP=${WORKER_IPS[$i]}
    WORKER_ID="worker-$((i+1))"
    
    echo "  Deploying $WORKER_ID on $WORKER_IP..."
    
    ssh ubuntu@$WORKER_IP "
        cd $PROJECT_DIR
        source venv/bin/activate
        nohup python chaos_cluster/worker_node.py \\
            --master http://$MASTER_IP:5000 \\
            --worker-id $WORKER_ID \\
            --fiber-count $FIBERS_PER_WORKER \\
            > logs/worker.log 2>&1 &
echo "  Worker PID: \$(cat logs/worker.pid)"
    "
    
    if [ $? -eq 0 ]; then
        echo "    ✓ $WORKER_ID deployed"
    else
        echo "    ✗ $WORKER_ID failed"
    fi
    
    sleep 2
done

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Monitoring commands:"
echo "  Master logs: ssh $MASTER_IP 'tail -f $PROJECT_DIR/logs/master.log'"
echo "  Status check: curl http://$MASTER_IP:5000/api/status | jq"
echo "  Start test: curl -X POST http://$MASTER_IP:5000/api/start"
echo "  Stop test:  curl -X POST http://$MASTER_IP:5000/api/stop"
echo ""
echo "Access the dashboard at: http://$MASTER_IP:5000/api/status"
