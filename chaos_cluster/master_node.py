#!/usr/bin/env python3
"""
Fiber Chaos Test - Master Node Controller

部署在中心节点（Target Node）上，负责：
1. 启动本地Fiber节点作为目标节点
2. 管理所有工作节点的连接
3. 协调混沌测试的执行
4. 收集统计信息

Usage:
    python master_node.py --config cluster_config.yaml
"""

import argparse
import sys
import os
import time
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from flask import Flask, request, jsonify
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework.basic_fiber import FiberTest
from framework.test_fiber import Fiber, FiberConfigPath

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class MasterNode:
    """中心节点控制器"""
    
    def __init__(self, config_path: str):
        self.config = self.load_config(config_path)
        self.test = None
        self.target_fiber = None
        self.worker_nodes = {}  # worker_id -> {ip, status, fiber_count}
        self.connected_workers = set()
        self.test_phase = "idle"  # idle, preparing, running, stopped
        self.stats = {
            'total_workers': 0,
            'total_fibers': 0,
            'connected_peers': 0,
            'channels': 0,
            'restart_count': 0,
            'disconnect_count': 0,
            'start_time': None,
            'errors': []
        }
        self.stop_event = threading.Event()
        
    def load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        import yaml
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def setup_target_node(self):
        """启动本地目标节点"""
        logger.info("Setting up target Fiber node...")
        
        self.test = FiberTest()
        self.test.node = self.test.CkbNode.init_dev_by_port(
            self.test.CkbNodeConfigPath.CURRENT_TEST,
            "chaos_master/node",
            8114,
            8125
        )
        self.test.node.prepare()
        self.test.node.start()
        
        # Mine initial blocks
        for i in range(10):
            self.test.Miner.miner_with_version(self.test.node, "0x0")
        
        # Start target fiber
        deploy_hash = "0x03c4475655a46dc4984c49fce03316f80bf666236bd95118112731082758d686"
        update_config = {
            "ckb_rpc_url": self.test.node.rpcUrl,
            "ckb_udt_whitelist": True,
            "xudt_script_code_hash": "0x102583443ba6cfe5a3ac268bbb4475fb63eb497dce077f126ad3b148d4f4f8f8",
            "xudt_cell_deps_tx_hash": deploy_hash,
            "xudt_cell_deps_index": 0,
        }
        
        self.target_fiber = Fiber.init_by_port(
            FiberConfigPath.CURRENT_DEV,
            self.test.Config.ACCOUNT_PRIVATE_1,
            "chaos_master/fiber_target",
            "8227",
            "8228"
        )
        self.target_fiber.prepare(update_config=update_config)
        self.target_fiber.start(fnn_log_level="info")
        
        logger.info(f"Target node started. Peer ID: {self.target_fiber.get_peer_id()}")
        logger.info(f"Target address: {self.target_fiber.get_client().node_info()['addresses'][0]}")
        
    def get_target_info(self) -> dict:
        """获取目标节点信息，供工作节点连接"""
        if not self.target_fiber:
            return {"error": "Target node not ready"}
        
        node_info = self.target_fiber.get_client().node_info()
        return {
            "peer_id": self.target_fiber.get_peer_id(),
            "address": node_info["addresses"][0],
            "node_id": node_info["node_id"],
            "status": "ready"
        }
    
    def register_worker(self, worker_id: str, worker_ip: str, fiber_count: int):
        """注册工作节点"""
        self.worker_nodes[worker_id] = {
            "ip": worker_ip,
            "fiber_count": fiber_count,
            "status": "registered",
            "registered_at": datetime.now().isoformat()
        }
        self.stats['total_workers'] += 1
        self.stats['total_fibers'] += fiber_count
        logger.info(f"Worker {worker_id} registered from {worker_ip} with {fiber_count} fibers")
        return {"status": "ok", "target_info": self.get_target_info()}
    
    def worker_ready(self, worker_id: str):
        """工作节点准备就绪"""
        if worker_id in self.worker_nodes:
            self.worker_nodes[worker_id]["status"] = "ready"
            self.connected_workers.add(worker_id)
            logger.info(f"Worker {worker_id} is ready. Total ready: {len(self.connected_workers)}")
        return {"status": "ok"}
    
    def update_stats(self, worker_id: str, stats: dict):
        """更新工作节点统计信息"""
        if worker_id in self.worker_nodes:
            self.worker_nodes[worker_id]["stats"] = stats
            self.worker_nodes[worker_id]["last_update"] = datetime.now().isoformat()
            
            # Aggregate stats
            self.stats['restart_count'] += stats.get('restart_count', 0)
            self.stats['disconnect_count'] += stats.get('disconnect_count', 0)
            if stats.get('errors'):
                self.stats['errors'].extend(stats['errors'])
    
    def start_chaos_test(self):
        """启动混沌测试"""
        logger.info("Starting chaos test...")
        self.test_phase = "running"
        self.stats['start_time'] = datetime.now()
        return {"status": "started"}
    
    def stop_chaos_test(self):
        """停止混沌测试"""
        logger.info("Stopping chaos test...")
        self.test_phase = "stopped"
        self.stop_event.set()
        return {"status": "stopped"}
    
    def get_status(self) -> dict:
        """获取整体状态"""
        if self.target_fiber:
            try:
                node_info = self.target_fiber.get_client().node_info()
                channels = self.target_fiber.get_client().list_channels({})
                self.stats['connected_peers'] = int(node_info.get("peers_count", "0x0"), 16)
                self.stats['channels'] = len(channels.get("channels", []))
            except Exception as e:
                logger.error(f"Error getting status: {e}")
        
        return {
            "phase": self.test_phase,
            "stats": self.stats,
            "workers": self.worker_nodes,
            "target_info": self.get_target_info()
        }
    
    def print_summary(self):
        """打印测试摘要"""
        if self.stats['start_time']:
            elapsed = datetime.now() - self.stats['start_time']
        else:
            elapsed = "N/A"
        
        print("\n" + "="*70)
        print("FIBER DISTRIBUTED CHAOS TEST SUMMARY")
        print("="*70)
        print(f"Total Duration: {elapsed}")
        print(f"Total Workers: {self.stats['total_workers']}")
        print(f"Total Fibers: {self.stats['total_fibers']}")
        print(f"Connected Peers: {self.stats['connected_peers']}")
        print(f"Total Channels: {self.stats['channels']}")
        print(f"Total Restarts: {self.stats['restart_count']}")
        print(f"Total Disconnects: {self.stats['disconnect_count']}")
        print(f"Total Errors: {len(self.stats['errors'])}")
        
        print("\nWorker Details:")
        for worker_id, info in self.worker_nodes.items():
            print(f"  {worker_id}: {info['ip']} - {info['status']}")
        print("="*70)


# Flask routes
master = None

@app.route('/api/target_info', methods=['GET'])
def api_target_info():
    return jsonify(master.get_target_info())

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    return jsonify(master.register_worker(
        data['worker_id'],
        data['worker_ip'],
        data['fiber_count']
    ))

@app.route('/api/ready', methods=['POST'])
def api_ready():
    data = request.json
    return jsonify(master.worker_ready(data['worker_id']))

@app.route('/api/stats', methods=['POST'])
def api_stats():
    data = request.json
    master.update_stats(data['worker_id'], data['stats'])
    return jsonify({"status": "ok"})

@app.route('/api/start', methods=['POST'])
def api_start():
    return jsonify(master.start_chaos_test())

@app.route('/api/stop', methods=['POST'])
def api_stop():
    return jsonify(master.stop_chaos_test())

@app.route('/api/status', methods=['GET'])
def api_status():
    return jsonify(master.get_status())


def main():
    parser = argparse.ArgumentParser(description='Fiber Chaos Test Master Node')
    parser.add_argument('--config', required=True, help='Path to config file')
    parser.add_argument('--port', type=int, default=5000, help='API server port')
    args = parser.parse_args()
    
    global master
    master = MasterNode(args.config)
    
    try:
        master.setup_target_node()
        
        # Start API server in a thread
        api_thread = threading.Thread(
            target=lambda: app.run(host='0.0.0.0', port=args.port, debug=False, use_reloader=False)
        )
        api_thread.daemon = True
        api_thread.start()
        
        logger.info(f"Master API server started on port {args.port}")
        logger.info("Waiting for workers to connect...")
        logger.info("Press Ctrl+C to stop")
        
        # Wait for interrupt
        while not master.stop_event.is_set():
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
    finally:
        master.print_summary()
        if master.target_fiber:
            master.target_fiber.stop()
            master.target_fiber.clean()
        if master.test and master.test.node:
            master.test.node.stop()
            master.test.node.clean()


if __name__ == '__main__':
    main()
