#!/usr/bin/env python3
"""
Fiber Network Chaos Testing Tool

A command-line tool for stress testing Fiber Network with multiple nodes,
where half of the nodes continuously restart and the other half continuously disconnect/reconnect.

Usage:
    python fiber_chaos_test.py --count 10 --duration 300
    python fiber_chaos_test.py -n 20 --target-index 0 --restart-interval 5 --disconnect-interval 3
"""

import argparse
import sys
import os
import time
import threading
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework.basic_fiber import FiberTest
from framework.test_fiber import Fiber, FiberConfigPath
from framework.util import generate_account_privakey, get_project_root
from framework.config import get_tmp_path


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('fiber_chaos_test.log')
    ]
)
logger = logging.getLogger(__name__)


class FiberChaosTest(FiberTest):
    """Fiber Network Chaos Testing Implementation"""
    
    # Type annotations for instance variables
    fibers = None  # type: List[Fiber]
    accounts = None  # type: List[str]
    target_fiber = None  # type: Optional[Fiber]
    restart_fibers = None  # type: List[Fiber]
    disconnect_fibers = None  # type: List[Fiber]
    
    def __init__(self):
        # Don't call super().__init__() to avoid pytest initialization
        self.fibers = []
        self.accounts = []
        self.target_fiber = None
        self.restart_fibers = []
        self.disconnect_fibers = []
        self.stop_event = threading.Event()
        self.stats = {
            'restart_count': 0,
            'disconnect_count': 0,
            'start_time': None,
            'errors': []
        }
        
    def setup_ckb_node(self):
        """Setup CKB dev node"""
        logger.info("Setting up CKB dev node...")
        self.node = self.CkbNode.init_dev_by_port(
            self.CkbNodeConfigPath.CURRENT_TEST, 
            "chaos_test/node", 
            8114, 
            8125
        )
        self.node.prepare()
        self.node.start()
        self.node.getClient().get_consensus()
        # Mine some blocks for funding
        for i in range(10):
            self.Miner.miner_with_version(self.node, "0x0")
        logger.info(f"CKB node started at {self.node.rpcUrl}")
        
    def generate_accounts(self, count: int, ckb_amount: int = 3000):
        """Generate N accounts and fund them with CKB"""
        logger.info(f"Generating {count} accounts with {ckb_amount} CKB each...")
        
        for i in range(count):
            # Generate new account
            private_key = generate_account_privakey()
            account = self.Ckb_cli.util_key_info_by_private_key(private_key)
            
            # Transfer CKB to new account
            tx_hash = self.Ckb_cli.wallet_transfer_by_private_key(
                self.Config.ACCOUNT_PRIVATE_1,
                account["address"]["testnet"],
                ckb_amount,
                self.node.rpcUrl,
            )
            self.Miner.miner_until_tx_committed(self.node, tx_hash, True)
            
            self.accounts.append(private_key)
            logger.info(f"Account {i+1}/{count} created: {account['address']['testnet']}")
            
        logger.info(f"Successfully created and funded {count} accounts")
        
    def start_fiber_nodes(self, count: int, base_rpc_port: int = 8500, base_p2p_port: int = 8600):
        """Start N Fiber nodes"""
        logger.info(f"Starting {count} Fiber nodes...")
        
        # Get UDT contract info for config
        deploy_hash = "0x03c4475655a46dc4984c49fce03316f80bf666236bd95118112731082758d686"
        deploy_index = 0
        
        for i in range(count):
            account_private = self.accounts[i]
            rpc_port = base_rpc_port + i
            p2p_port = base_p2p_port + i
            
            # Create fiber config
            update_config = {
                "ckb_rpc_url": self.node.rpcUrl,
                "ckb_udt_whitelist": True,
                "xudt_script_code_hash": "0x102583443ba6cfe5a3ac268bbb4475fb63eb497dce077f126ad3b148d4f4f8f8",
                "xudt_cell_deps_tx_hash": deploy_hash,
                "xudt_cell_deps_index": deploy_index,
            }
            
            # Initialize and start fiber
            fiber = Fiber.init_by_port(
                FiberConfigPath.CURRENT_DEV,
                account_private,
                f"chaos_test/fiber_{i}",
                str(rpc_port),
                str(p2p_port),
            )
            
            fiber.prepare(update_config=update_config)
            fiber.start(fnn_log_level="info")
            
            self.fibers.append(fiber)
            logger.info(f"Fiber node {i+1}/{count} started on RPC port {rpc_port}, P2P port {p2p_port}")
            
            # Small delay to avoid resource contention
            time.sleep(0.5)
            
        logger.info(f"All {count} Fiber nodes started successfully")
        
    def setup_target_node(self, target_index: int = 0):
        """Setup the target node that other nodes will connect to"""
        self.target_fiber = self.fibers[target_index]
        logger.info(f"Target node set to Fiber {target_index}")
        logger.info(f"Target Peer ID: {self.target_fiber.get_peer_id()}")
        
    def open_channels_with_target(self, funding_amount: int = 10000000000):
        """Open channels from all nodes to the target node"""
        logger.info(f"Opening channels to target node with funding amount {funding_amount}...")
        
        for i, fiber in enumerate(self.fibers):
            if fiber == self.target_fiber:
                continue
                
            try:
                # Connect to target
                fiber.connect_peer(self.target_fiber)
                time.sleep(1)
                
                # Get target's auto-accept minimum
                min_funding = int(
                    self.target_fiber.get_client().node_info()[
                        "open_channel_auto_accept_min_ckb_funding_amount"
                    ],
                    16,
                )
                
                # Open channel
                open_channel_config = {
                    "peer_id": self.target_fiber.get_peer_id(),
                    "funding_amount": hex(funding_amount),
                    "tlc_fee_proportional_millionths": hex(1000),
                    "public": True,
                }
                
                result = fiber.get_client().open_channel(open_channel_config)
                logger.info(f"Channel opened from Fiber {i} to target: {result.get('temporary_channel_id', 'N/A')}")
                
                # Wait a bit for channel negotiation
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Failed to open channel from Fiber {i}: {e}")
                
        logger.info("Channel setup completed")
        
    def split_groups(self):
        """Split fibers into restart group and disconnect group"""
        other_fibers = [f for f in self.fibers if f != self.target_fiber]
        mid = len(other_fibers) // 2
        
        self.restart_fibers = other_fibers[:mid]
        self.disconnect_fibers = other_fibers[mid:]
        
        logger.info(f"Split into {len(self.restart_fibers)} restart nodes and {len(self.disconnect_fibers)} disconnect nodes")
        
    def restart_worker(self, fiber: Fiber, interval: float):
        """Worker thread that continuously restarts a fiber node"""
        fiber_id = self.fibers.index(fiber)
        
        while not self.stop_event.is_set():
            try:
                logger.debug(f"[Restart-{fiber_id}] Stopping fiber...")
                fiber.stop()
                time.sleep(1)
                
                logger.debug(f"[Restart-{fiber_id}] Starting fiber...")
                fiber.start(fnn_log_level="info")
                
                self.stats['restart_count'] += 1
                logger.info(f"[Restart-{fiber_id}] Restarted (total: {self.stats['restart_count']})")
                
            except Exception as e:
                error_msg = f"[Restart-{fiber_id}] Error: {e}"
                logger.error(error_msg)
                self.stats['errors'].append(error_msg)
                
            # Wait for interval or until stopped
            self.stop_event.wait(interval)
            
    def disconnect_worker(self, fiber: Fiber, interval: float):
        """Worker thread that continuously disconnects and reconnects"""
        fiber_id = self.fibers.index(fiber)
        target_peer_id = self.target_fiber.get_peer_id()
        
        while not self.stop_event.is_set():
            try:
                logger.debug(f"[Disconnect-{fiber_id}] Disconnecting from target...")
                fiber.get_client().disconnect_peer({"peer_id": target_peer_id})
                time.sleep(2)
                
                logger.debug(f"[Disconnect-{fiber_id}] Reconnecting to target...")
                fiber.connect_peer(self.target_fiber)
                
                self.stats['disconnect_count'] += 1
                logger.info(f"[Disconnect-{fiber_id}] Disconnected/reconnected (total: {self.stats['disconnect_count']})")
                
            except Exception as e:
                error_msg = f"[Disconnect-{fiber_id}] Error: {e}"
                logger.error(error_msg)
                self.stats['errors'].append(error_msg)
                
            # Wait for interval or until stopped
            self.stop_event.wait(interval)
            
    def monitor_worker(self, interval: float):
        """Worker thread that monitors the network status"""
        while not self.stop_event.is_set():
            try:
                # Get target node info
                node_info = self.target_fiber.get_client().node_info()
                peer_count = int(node_info.get("peers_count", "0x0"), 16)
                channel_count = int(node_info.get("channel_count", "0x0"), 16)
                
                # Get channels info
                channels = self.target_fiber.get_client().list_channels({})
                active_channels = len([c for c in channels.get("channels", []) 
                                     if c["state"]["state_name"] == "ChannelReady"])
                
                elapsed = datetime.now() - self.stats['start_time']
                logger.info(f"[Monitor] Peers: {peer_count}, Channels: {channel_count}, "
                          f"Active: {active_channels}, Restarts: {self.stats['restart_count']}, "
                          f"Disconnects: {self.stats['disconnect_count']}, Elapsed: {elapsed}")
                
            except Exception as e:
                logger.error(f"[Monitor] Error: {e}")
                
            self.stop_event.wait(interval)
            
    def run_chaos_test(self, restart_interval: float, disconnect_interval: float, 
                      monitor_interval: float = 10.0):
        """Run the chaos test with all workers"""
        logger.info("Starting chaos test...")
        self.stats['start_time'] = datetime.now()
        
        threads = []
        
        # Start restart workers
        for fiber in self.restart_fibers:
            t = threading.Thread(target=self.restart_worker, args=(fiber, restart_interval))
            t.daemon = True
            t.start()
            threads.append(t)
            logger.info(f"Started restart worker for Fiber {self.fibers.index(fiber)}")
            
        # Start disconnect workers
        for fiber in self.disconnect_fibers:
            t = threading.Thread(target=self.disconnect_worker, args=(fiber, disconnect_interval))
            t.daemon = True
            t.start()
            threads.append(t)
            logger.info(f"Started disconnect worker for Fiber {self.fibers.index(fiber)}")
            
        # Start monitor worker
        monitor_thread = threading.Thread(target=self.monitor_worker, args=(monitor_interval,))
        monitor_thread.daemon = True
        monitor_thread.start()
        threads.append(monitor_thread)
        logger.info("Started monitor worker")
        
        return threads
        
    def stop_chaos_test(self):
        """Stop all chaos test workers"""
        logger.info("Stopping chaos test...")
        self.stop_event.set()
        time.sleep(2)  # Give threads time to stop
        
    def cleanup(self):
        """Cleanup all resources"""
        logger.info("Cleaning up...")
        
        # Stop all fibers
        for fiber in self.fibers:
            try:
                fiber.stop()
                fiber.clean()
            except Exception as e:
                logger.error(f"Error cleaning up fiber: {e}")
                
        # Stop CKB node
        try:
            self.node.stop()
            self.node.clean()
        except Exception as e:
            logger.error(f"Error cleaning up CKB node: {e}")
            
        logger.info("Cleanup completed")
        
    def print_summary(self):
        """Print test summary"""
        elapsed = datetime.now() - self.stats['start_time']
        
        print("\n" + "="*60)
        print("FIBER CHAOS TEST SUMMARY")
        print("="*60)
        print(f"Total Duration: {elapsed}")
        print(f"Total Nodes: {len(self.fibers)}")
        print(f"Restart Group Size: {len(self.restart_fibers)}")
        print(f"Disconnect Group Size: {len(self.disconnect_fibers)}")
        print(f"Total Restarts: {self.stats['restart_count']}")
        print(f"Total Disconnects: {self.stats['disconnect_count']}")
        print(f"Total Errors: {len(self.stats['errors'])}")
        
        if self.stats['errors']:
            print("\nErrors encountered:")
            for i, error in enumerate(self.stats['errors'][:10]):  # Show first 10
                print(f"  {i+1}. {error}")
            if len(self.stats['errors']) > 10:
                print(f"  ... and {len(self.stats['errors']) - 10} more errors")
                
        print("="*60)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Fiber Network Chaos Testing Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with 10 nodes for 5 minutes
  python fiber_chaos_test.py --count 10 --duration 300
  
  # Run with 20 nodes, custom intervals
  python fiber_chaos_test.py -n 20 --restart-interval 5 --disconnect-interval 3
  
  # Run with specific target and funding amounts
  python fiber_chaos_test.py --count 10 --target-index 0 --ckb-amount 5000 --funding-amount 20000000000
        """
    )
    
    parser.add_argument('-n', '--count', type=int, default=10,
                       help='Number of Fiber nodes to create (default: 10)')
    parser.add_argument('--target-index', type=int, default=0,
                       help='Index of the target node (default: 0)')
    parser.add_argument('--duration', type=int, default=None,
                       help='Test duration in seconds (default: run until interrupted)')
    parser.add_argument('--restart-interval', type=float, default=10.0,
                       help='Interval between restarts in seconds (default: 10)')
    parser.add_argument('--disconnect-interval', type=float, default=5.0,
                       help='Interval between disconnects in seconds (default: 5)')
    parser.add_argument('--monitor-interval', type=float, default=10.0,
                       help='Monitoring output interval in seconds (default: 10)')
    parser.add_argument('--ckb-amount', type=int, default=3000,
                       help='CKB amount to fund each account (default: 3000)')
    parser.add_argument('--funding-amount', type=int, default=10000000000,
                       help='Channel funding amount in shannons (default: 10000000000 = 100 CKB)')
    parser.add_argument('--base-rpc-port', type=int, default=8500,
                       help='Base RPC port number (default: 8500)')
    parser.add_argument('--base-p2p-port', type=int, default=8600,
                       help='Base P2P port number (default: 8600)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose (debug) logging')
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate arguments
    if args.count < 3:
        print("Error: At least 3 nodes are required (1 target + 1 restart + 1 disconnect)")
        sys.exit(1)
        
    if args.target_index >= args.count:
        print(f"Error: Target index {args.target_index} is out of range (0-{args.count-1})")
        sys.exit(1)
        
    print(f"""
Fiber Chaos Test Configuration:
  Node Count: {args.count}
  Target Index: {args.target_index}
  Duration: {args.duration if args.duration else 'Unlimited (Ctrl+C to stop)'} seconds
  Restart Interval: {args.restart_interval}s
  Disconnect Interval: {args.disconnect_interval}s
  CKB per Account: {args.ckb_amount}
  Channel Funding: {args.funding_amount} shannons
  Base RPC Port: {args.base_rpc_port}
  Base P2P Port: {args.base_p2p_port}
""")
    
    test = FiberChaosTest()
    
    try:
        # Setup phase
        print("\n[Phase 1] Setting up CKB node...")
        test.setup_ckb_node()
        
        print(f"\n[Phase 2] Generating {args.count} accounts...")
        test.generate_accounts(args.count, args.ckb_amount)
        
        print(f"\n[Phase 3] Starting {args.count} Fiber nodes...")
        test.start_fiber_nodes(args.count, args.base_rpc_port, args.base_p2p_port)
        
        print(f"\n[Phase 4] Setting up target node (index {args.target_index})...")
        test.setup_target_node(args.target_index)
        
        print("\n[Phase 5] Opening channels with target node...")
        test.open_channels_with_target(args.funding_amount)
        
        print("\n[Phase 6] Splitting into groups...")
        test.split_groups()
        
        print("\n[Phase 7] Starting chaos test...")
        print("Press Ctrl+C to stop\n")
        threads = test.run_chaos_test(
            args.restart_interval,
            args.disconnect_interval,
            args.monitor_interval
        )
        
        # Run for specified duration or until interrupted
        if args.duration:
            time.sleep(args.duration)
        else:
            # Run indefinitely until Ctrl+C
            while True:
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        logger.exception("Unexpected error occurred")
        print(f"\nError: {e}")
    finally:
        # Cleanup
        test.stop_chaos_test()
        test.print_summary()
        test.cleanup()
        
    print("\nTest completed!")


if __name__ == "__main__":
    main()
