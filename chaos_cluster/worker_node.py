#!/usr/bin/env python3
"""
Fiber Chaos Test - Worker Node

部署在N台工作机器上，每台机器运行M个Fiber节点，负责：
1. 创建M个账户并获取资金
2. 启动M个Fiber节点
3. 连接到中心节点并建立Channel
4. 执行重启+disconnect混沌测试
5. 上报统计信息到Master

Usage:
    python worker_node.py --master http://master-ip:5000 --worker-id worker-1 --fiber-count 5
"""

import argparse
import sys
import os
import time
import json
import threading
import requests
import logging
from datetime import datetime
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework.basic_fiber import FiberTest
from framework.test_fiber import Fiber, FiberConfigPath
from framework.util import generate_account_privakey

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WorkerNode:
    """工作节点"""
    
    def __init__(self, master_url: str, worker_id: str, fiber_count: int, 
                 base_rpc_port: int = 8500, base_p2p_port: int = 8600):
        self.master_url = master_url.rstrip('/')
        self.worker_id = worker_id
        self.fiber_count = fiber_count
        self.base_rpc_port = base_rpc_port
        self.base_p2p_port = base_p2p_port
        
        self.test = None
        self.accounts = []
        self.fibers = []
        self.target_info = None
        self.stop_event = threading.Event()
        self.stats = {
            'restart_count': 0,
            'disconnect_count': 0,
            'start_time': None,
            'errors': []
        }
        self.worker_threads = []
        
    def get_target_info(self) -> dict:
        """从Master获取目标节点信息"""
        try:
            resp = requests.get(f"{self.master_url}/api/target_info")
            if resp.status_code == 200:
                return resp.json()
            else:
                raise Exception(f"Failed to get target info: {resp.text}")
        except Exception as e:
            logger.error(f"Error getting target info: {e}")
            raise
    
    def register_with_master(self):
        """向Master注册"""
        import socket
        worker_ip = socket.gethostname()
        
        data = {
            "worker_id": self.worker_id,
            "worker_ip": worker_ip,
            "fiber_count": self.fiber_count
        }
        
        try:
            resp = requests.post(f"{self.master_url}/api/register", json=data)
            if resp.status_code == 200:
                result = resp.json()
                self.target_info = result.get("target_info")
                logger.info(f"Registered with master. Target: {self.target_info['peer_id']}")
                return True
            else:
                logger.error(f"Registration failed: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Error registering: {e}")
            return False
    
    def notify_ready(self):
        """通知Master准备就绪"""
        data = {"worker_id": self.worker_id}
        try:
            resp = requests.post(f"{self.master_url}/api/ready", json=data)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Error notifying ready: {e}")
            return False
    
    def report_stats(self):
        """上报统计信息"""
        data = {
            "worker_id": self.worker_id,
            "stats": self.stats
        }
        try:
            requests.post(f"{self.master_url}/api/stats", json=data)
        except Exception as e:
            logger.debug(f"Error reporting stats: {e}")
    
    def setup_ckb_funding(self):
        """设置CKB资金 - 工作节点不需要本地CKB节点，通过Master的Faucet获取资金"""
        logger.info("Setting up CKB funding via master...")
        
        # 创建test对象来访问必要的工具
        self.test = FiberTest()
        
        # 注意：这里我们假设有一个faucet服务或者Master提供资金
        # 实际实现可能需要调用Master的API来获取资金
        # 简化版本：使用Master提供的账户资金配置
        
        for i in range(self.fiber_count):
            # 生成账户
            private_key = generate_account_privakey()
            self.accounts.append(private_key)
            logger.info(f"Generated account {i+1}/{self.fiber_count}")
            
    def start_fiber_nodes(self):
        """启动所有Fiber节点"""
        logger.info(f"Starting {self.fiber_count} Fiber nodes...")
        
        deploy_hash = "0x03c4475655a46dc4984c49fce03316f80bf666236bd95118112731082758d686"
        update_config = {
            "ckb_rpc_url": self.target_info.get("ckb_rpc_url", "http://master:8114"),
            "ckb_udt_whitelist": True,
            "xudt_script_code_hash": "0x102583443ba6cfe5a3ac268bbb4475fb63eb497dce077f126ad3b148d4f4f8f8",
            "xudt_cell_deps_tx_hash": deploy_hash,
            "xudt_cell_deps_index": 0,
        }
        
        for i in range(self.fiber_count):
            fiber = Fiber.init_by_port(
                FiberConfigPath.CURRENT_DEV,
                self.accounts[i],
                f"chaos_worker/{self.worker_id}/fiber_{i}",
                str(self.base_rpc_port + i),
                str(self.base_p2p_port + i)
            )
            
            fiber.prepare(update_config=update_config)
            fiber.start(fnn_log_level="info")
            self.fibers.append(fiber)
            
            logger.info(f"Fiber {i+1}/{self.fiber_count} started on port {self.base_rpc_port + i}")
            time.sleep(0.5)
    
    def connect_to_target(self):
        """连接到目标节点并建立Channel"""
        logger.info("Connecting to target node...")
        
        target_address = self.target_info['address']
        target_peer_id = self.target_info['peer_id']
        
        for i, fiber in enumerate(self.fibers):
            try:
                # Connect to target
                fiber.get_client().connect_peer({"address": target_address})
                time.sleep(1)
                
                # Open channel (simplified version)
                open_channel_config = {
                    "peer_id": target_peer_id,
                    "funding_amount": hex(10000000000),  # 100 CKB
                    "tlc_fee_proportional_millionths": hex(1000),
                    "public": True,
                }
                
                result = fiber.get_client().open_channel(open_channel_config)
                logger.info(f"Channel opened from Fiber {i}: {result.get('temporary_channel_id', 'N/A')}")
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Failed to connect Fiber {i}: {e}")
                self.stats['errors'].append(f"Fiber {i} connection failed: {str(e)}")
    
    def chaos_worker(self, fiber: Fiber, fiber_index: int):
        """单个Fiber的混沌测试工作线程"""
        target_peer_id = self.target_info['peer_id']
        
        while not self.stop_event.is_set():
            try:
                # Restart operation
                logger.debug(f"[{self.worker_id}-Fiber{fiber_index}] Restarting...")
                fiber.stop()
                time.sleep(1)
                fiber.start(fnn_log_level="info")
                self.stats['restart_count'] += 1
                
                # Reconnect after restart
                time.sleep(2)
                fiber.get_client().connect_peer({
                    "address": self.target_info['address']
                })
                
                # Disconnect operation
                time.sleep(random.uniform(3, 8))
                logger.debug(f"[{self.worker_id}-Fiber{fiber_index}] Disconnecting...")
                fiber.get_client().disconnect_peer({"peer_id": target_peer_id})
                time.sleep(2)
                
                # Reconnect
                fiber.get_client().connect_peer({
                    "address": self.target_info['address']
                })
                self.stats['disconnect_count'] += 1
                
                logger.info(f"[{self.worker_id}-Fiber{fiber_index}] Cycle completed. "
                          f"Restarts: {self.stats['restart_count']}, "
                          f"Disconnects: {self.stats['disconnect_count']}")
                
            except Exception as e:
                error_msg = f"[{self.worker_id}-Fiber{fiber_index}] Error: {e}"
                logger.error(error_msg)
                self.stats['errors'].append(error_msg)
                time.sleep(5)
    
    def start_chaos_test(self):
        """启动混沌测试"""
        logger.info("Starting chaos test...")
        self.stats['start_time'] = datetime.now()
        
        # Start chaos workers for each fiber
        for i, fiber in enumerate(self.fibers):
            t = threading.Thread(target=self.chaos_worker, args=(fiber, i))
            t.daemon = True
            t.start()
            self.worker_threads.append(t)
            logger.info(f"Started chaos worker for Fiber {i}")
    
    def stats_reporter(self):
        """统计信息上报线程"""
        while not self.stop_event.is_set():
            self.report_stats()
            self.stop_event.wait(10)  # Report every 10 seconds
    
    def wait_for_start_signal(self):
        """等待Master的开始信号"""
        logger.info("Waiting for start signal from master...")
        while not self.stop_event.is_set():
            try:
                resp = requests.get(f"{self.master_url}/api/status")
                if resp.status_code == 200:
                    status = resp.json()
                    if status.get('phase') == 'running':
                        logger.info("Received start signal!")
                        return True
            except Exception as e:
                logger.debug(f"Error checking status: {e}")
            
            time.sleep(2)
        return False
    
    def run(self):
        """运行工作节点"""
        try:
            # 1. Get target info and register
            if not self.register_with_master():
                return False
            
            # 2. Setup accounts
            self.setup_ckb_funding()
            
            # 3. Start fibers
            self.start_fiber_nodes()
            
            # 4. Connect to target
            self.connect_to_target()
            
            # 5. Notify ready
            self.notify_ready()
            logger.info("Worker is ready, waiting for start signal...")
            
            # 6. Wait for start signal
            if not self.wait_for_start_signal():
                return False
            
            # 7. Start chaos test
            self.start_chaos_test()
            
            # 8. Start stats reporter
            stats_thread = threading.Thread(target=self.stats_reporter)
            stats_thread.daemon = True
            stats_thread.start()
            
            # 9. Wait for stop signal
            logger.info("Chaos test running. Press Ctrl+C to stop.")
            while not self.stop_event.is_set():
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("\nInterrupted by user")
        except Exception as e:
            logger.exception("Unexpected error")
        finally:
            self.cleanup()
        
        return True
    
    def cleanup(self):
        """清理资源"""
        logger.info("Cleaning up...")
        self.stop_event.set()
        
        # Stop all fibers
        for fiber in self.fibers:
            try:
                fiber.stop()
                fiber.clean()
            except Exception as e:
                logger.error(f"Error cleaning up fiber: {e}")
        
        # Final stats report
        self.report_stats()
        
        logger.info("Cleanup completed")


def main():
    parser = argparse.ArgumentParser(description='Fiber Chaos Test Worker Node')
    parser.add_argument('--master', required=True, help='Master node URL (http://ip:port)')
    parser.add_argument('--worker-id', required=True, help='Unique worker ID')
    parser.add_argument('--fiber-count', type=int, default=5, help='Number of fibers on this worker')
    parser.add_argument('--base-rpc-port', type=int, default=8500, help='Base RPC port')
    parser.add_argument('--base-p2p-port', type=int, default=8600, help='Base P2P port')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print(f"""
Fiber Chaos Worker Node
=======================
Worker ID: {args.worker_id}
Master: {args.master}
Fiber Count: {args.fiber_count}
Base RPC Port: {args.base_rpc_port}
Base P2P Port: {args.base_p2p_port}
""")
    
    worker = WorkerNode(
        args.master,
        args.worker_id,
        args.fiber_count,
        args.base_rpc_port,
        args.base_p2p_port
    )
    
    worker.run()


if __name__ == '__main__':
    main()
