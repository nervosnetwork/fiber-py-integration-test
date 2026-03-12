#!/bin/bash
# Deploy Fiber Chaos Test Cluster
# 部署Fiber混沌测试集群

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
MASTER_HOST=""
CONFIG_FILE="chaos_cluster/config.yaml"
MODE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --master)
      MASTER_HOST="$2"
      shift 2
      ;;
    --config)
      CONFIG_FILE="$2"
      shift 2
      ;;
    --mode)
      MODE="$2"
      shift 2
      ;;
    --help)
      echo "Usage: $0 --mode <master|worker> --master <master-ip> [options]"
      echo ""
      echo "Options:"
      echo "  --mode <mode>        Deployment mode: master or worker"
      echo "  --master <ip>        Master node IP address (required for worker mode)"
      echo "  --config <file>      Config file path (default: chaos_cluster/config.yaml)"
      echo "  --help               Show this help message"
      echo ""
      echo "Examples:"
      echo "  # Deploy master node"
      echo "  $0 --mode master"
      echo ""
      echo "  # Deploy worker node"
      echo "  $0 --mode worker --master 192.168.1.100"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Validate mode
if [ -z "$MODE" ]; then
  echo -e "${RED}Error: --mode is required${NC}"
  exit 1
fi

if [ "$MODE" != "master" ] && [ "$MODE" != "worker" ]; then
  echo -e "${RED}Error: --mode must be 'master' or 'worker'${NC}"
  exit 1
fi

# Function to check if required commands exist
check_requirements() {
  echo "Checking requirements..."
  
  # Check Python
  if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed${NC}"
    exit 1
  fi
  
  # Check if we're in the right directory
  if [ ! -f "framework/basic_fiber.py" ]; then
    echo -e "${RED}Error: Must run from project root directory${NC}"
    exit 1
  fi
  
  # Check required Python packages
  python3 -c "import flask, requests, yaml" 2>/dev/null || {
    echo -e "${YELLOW}Warning: Missing Python packages. Installing...${NC}"
    pip3 install flask requests pyyaml
  }
  
  echo -e "${GREEN}✓ Requirements check passed${NC}"
}

# Function to deploy master node
deploy_master() {
  echo -e "${GREEN}Deploying Master Node...${NC}"
  
  # Check config file
  if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: Config file not found: $CONFIG_FILE${NC}"
    exit 1
  fi
  
  echo "Starting Master Node..."
  echo "Config: $CONFIG_FILE"
  
  # Create log directory
  mkdir -p logs
  
  # Start master node
  nohup python3 chaos_cluster/master_node.py \
    --config "$CONFIG_FILE" \
    --port 5000 \
    > logs/master_node.log 2>&1 &
  
  MASTER_PID=$!
  echo $MASTER_PID > logs/master_node.pid
  
  echo -e "${GREEN}✓ Master node started with PID $MASTER_PID${NC}"
  echo ""
  echo "Logs: tail -f logs/master_node.log"
  echo "API: http://localhost:5000"
  echo ""
  echo "Worker nodes can connect using:"
  echo "  python3 chaos_cluster/worker_node.py --master http://<this-host-ip>:5000 --worker-id <worker-name>"
}

# Function to deploy worker node
deploy_worker() {
  if [ -z "$MASTER_HOST" ]; then
    echo -e "${RED}Error: --master is required for worker mode${NC}"
    exit 1
  fi
  
  echo -e "${GREEN}Deploying Worker Node...${NC}"
  echo "Master: $MASTER_HOST:5000"
  
  # Generate worker ID if not provided
  WORKER_ID=${WORKER_ID:-"worker-$(hostname)-$(date +%s)"}
  
  echo "Worker ID: $WORKER_ID"
  
  # Get fiber count from config or use default
  FIBER_COUNT=${FIBER_COUNT:-5}
  echo "Fiber Count: $FIBER_COUNT"
  
  # Create log directory
  mkdir -p logs
  
  # Start worker node
  nohup python3 chaos_cluster/worker_node.py \
    --master "http://$MASTER_HOST:5000" \
    --worker-id "$WORKER_ID" \
    --fiber-count "$FIBER_COUNT" \
    > logs/worker_node.log 2>&1 &
  
  WORKER_PID=$!
  echo $WORKER_PID > logs/worker_node.pid
  
  echo -e "${GREEN}✓ Worker node started with PID $WORKER_PID${NC}"
  echo ""
  echo "Logs: tail -f logs/worker_node.log"
}

# Function to stop nodes
stop_nodes() {
  echo "Stopping Fiber Chaos Test nodes..."
  
  if [ -f "logs/master_node.pid" ]; then
    PID=$(cat logs/master_node.pid)
    if kill -0 $PID 2>/dev/null; then
      kill $PID
      echo "✓ Stopped master node (PID $PID)"
    fi
    rm -f logs/master_node.pid
  fi
  
  if [ -f "logs/worker_node.pid" ]; then
    PID=$(cat logs/worker_node.pid)
    if kill -0 $PID 2>/dev/null; then
      kill $PID
      echo "✓ Stopped worker node (PID $PID)"
    fi
    rm -f logs/worker_node.pid
  fi
}

# Function to show status
show_status() {
  echo "Fiber Chaos Test Status"
  echo "======================="
  
  if [ -f "logs/master_node.pid" ]; then
    PID=$(cat logs/master_node.pid)
    if kill -0 $PID 2>/dev/null; then
      echo -e "Master Node: ${GREEN}Running${NC} (PID $PID)"
    else
      echo -e "Master Node: ${RED}Not running${NC}"
    fi
  else
    echo -e "Master Node: ${RED}Not running${NC}"
  fi
  
  if [ -f "logs/worker_node.pid" ]; then
    PID=$(cat logs/worker_node.pid)
    if kill -0 $PID 2>/dev/null; then
      echo -e "Worker Node: ${GREEN}Running${NC} (PID $PID)"
    else
      echo -e "Worker Node: ${RED}Not running${NC}"
    fi
  else
    echo -e "Worker Node: ${RED}Not running${NC}"
  fi
}

# Main logic
case "$MODE" in
  master)
    check_requirements
    deploy_master
    ;;
  worker)
    check_requirements
    deploy_worker
    ;;
  stop)
    stop_nodes
    ;;
  status)
    show_status
    ;;
  *)
    echo -e "${RED}Error: Unknown mode '$MODE'${NC}"
    exit 1
    ;;
esac
