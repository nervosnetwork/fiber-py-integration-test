import time
import pytest
import threading
import random
from framework.basic_fiber import FiberTest
from framework.chaos.proxy import ChaosProxy
from framework.chaos.toxiproxy import ToxiproxyClient
from framework.rpc import RPCClient
from framework.util import hex_timestamp_to_datetime


class TestChaosDemo(FiberTest):
    """
    Chaos Engineering Demo Tests for Fiber Network.
    
    This suite demonstrates how to inject faults (chaos) into the Fiber network
    and verify the system's resilience and recovery capabilities.
    """

    def test_node_crash_and_recovery(self):
        """
        Scenario: Node Crash and Recovery
        
        1. Setup a 2-node Fiber network with an open channel.
        2. Verify connectivity and perform an initial payment.
        3. CHAOS: Forcefully kill one fiber node (Fiber2) to simulate a crash.
        4. RECOVERY: Restart the crashed node.
        5. Verify the node recovers and can rejoin the network.
        6. Verify channel state is restored and payments can continue.
        """

        # 1. Setup is handled by setup_method in FiberTest
        # We have self.fiber1 and self.fiber2

        # Open channel between fiber1 and fiber2
        self.open_channel(self.fiber1, self.fiber2, 10000000, 10000000)

        # 2. Verify connectivity with a payment
        print("\n[Chaos] Performing initial payment check...")
        payment_hash = self.send_payment(self.fiber1, self.fiber2, 1000)
        self.wait_payment_state(self.fiber1, payment_hash, "Success")
        print("[Chaos] Initial payment successful.")

        # 3. CHAOS: Forcefully stop Fiber2
        print("\n[Chaos] 💥 INJECTING FAULT: Forcefully killing Fiber2...")
        self.fiber2.force_stop()

        # Verify Fiber2 is down (RPC should fail)
        print("[Chaos] Verifying Fiber2 is down...")
        try:
            self.fiber2.get_client().node_info()
            assert False, "Fiber2 should be down but RPC is still responding"
        except Exception:
            print("[Chaos] Fiber2 is confirmed down (RPC unreachable).")

        # 4. RECOVERY: Restart Fiber2
        print("\n[Chaos] 🚑 RECOVERY: Restarting Fiber2...")
        # Start using the same configuration and data directory
        self.fiber2.start()

        # Wait for node to be ready
        print("[Chaos] Waiting for Fiber2 to initialize...")
        time.sleep(5)  # Give it some time to boot

        # 5. Verify Node Recovery
        node_info = self.fiber2.get_client().node_info()
        print(f"[Chaos] Fiber2 recovered. Node ID: {node_info['node_id']}")

        # Re-connect peers (in case p2p connection was lost and not auto-reconnected immediately)
        # Note: Fiber might auto-reconnect, but explicit connection ensures test stability
        print("[Chaos] Re-establishing P2P connection...")
        try:
            self.fiber1.connect_peer(self.fiber2)
        except Exception as e:
            print(f"[Chaos] Connect peer info (might be already connected): {e}")

        # 6. Verify Channel State and Business Continuity
        print("[Chaos] Verifying channel state restored...")
        # Wait for channel to be ready again
        self.wait_for_channel_state(self.fiber1.get_client(), self.fiber2.get_peer_id(), "ChannelReady")

        print("\n[Chaos] Performing post-recovery payment check...")
        payment_hash_2 = self.send_payment(self.fiber1, self.fiber2, 2000)
        self.wait_payment_state(self.fiber1, payment_hash_2, "Success")
        print("[Chaos] Post-recovery payment successful. System resilience verified! 🎉")

    def test_network_partition_simulation(self):
        """
        Scenario: Temporary Network Partition (Simulated by stopping one node)
        
        In a real chaos test, we might use iptables to block traffic. 
        Here we simulate it by stopping and restarting, focusing on channel state persistence.
        """
        self.open_channel(self.fiber1, self.fiber2, 10000000, 10000000)

        # Check balance before
        balance_before = self.get_fiber_balance(self.fiber1)

        print("\n[Chaos] Stopping Fiber1 to simulate disconnect...")
        self.fiber1.stop()
        time.sleep(2)

        print("[Chaos] Restarting Fiber1...")
        self.fiber1.start()
        time.sleep(5)

        print("[Chaos] Verifying balance persistence...")
        balance_after = self.get_fiber_balance(self.fiber1)

        # We need to wait for channels to be loaded
        self.wait_for_channel_state(self.fiber1.get_client(), self.fiber2.get_peer_id(), "ChannelReady")

        # Verify balances match (ignoring slight variations if any automated fees occurred, but here should be exact)
        # Note: get_fiber_balance returns a complex dict, simplifying check for demo
        assert balance_after['chain']['ckb'] == balance_before['chain']['ckb'], "Chain balance should persist"
        print("[Chaos] State persistence verified.")

    def test_network_flapping(self):
        """
        Scenario: Network Flapping (Unstable Connection)
        
        1. Setup 2 nodes and a channel.
        2. Start a background thread that randomly disconnects and reconnects peers every few seconds.
        3. Attempt to send a series of payments while the network is unstable.
        4. Stop the interference.
        5. Verify that the network stabilizes and payments work consistently again.
        """
        self.open_channel(self.fiber1, self.fiber2, 10000000, 10000000)

        # Prepare background thread for flapping
        stop_flapping = threading.Event()

        def flapping_task():
            print("\\n[Chaos] 🌪️ Network flapping started...")
            while not stop_flapping.is_set():
                time.sleep(random.uniform(0.5, 1.5))
                if stop_flapping.is_set():
                    break

                # Randomly choose to disconnect or connect
                action = random.choice(['disconnect', 'connect'])
                try:
                    if action == 'disconnect':
                        # print("[Chaos] 🔌 Simulating disconnect...")
                        self.fiber1.get_client().disconnect_peer({"peer_id": self.fiber2.get_peer_id()})
                    else:
                        # print("[Chaos] 🔗 Simulating connect...")
                        self.fiber1.connect_peer(self.fiber2)
                except Exception as e:
                    # Ignore errors during chaos (e.g. already connected/disconnected)
                    pass
            print("[Chaos] 🌪️ Network flapping stopped.")

        flapping_thread = threading.Thread(target=flapping_task)
        flapping_thread.start()

        # Try sending payments during chaos
        print("\\n[Chaos] Attempting payments during instability...")
        success_count = 0
        total_attempts = 10

        for i in range(total_attempts):
            try:
                # Wait a bit between attempts
                time.sleep(1)
                print(f"[Chaos] Payment attempt {i + 1}/{total_attempts}...")
                payment_hash = self.send_payment(self.fiber1, self.fiber2, 100)
                # We don't wait strictly for success here, as it might timeout or fail
                # But if send_payment returns, we check status briefly
                self.wait_payment_state(self.fiber1, payment_hash, "Success", timeout=3)
                print(f"[Chaos] Payment {i + 1} SUCCESS")
                success_count += 1
            except Exception as e:
                print(f"[Chaos] Payment {i + 1} FAILED (Expected): {e}")

        print(f"\\n[Chaos] Chaos phase ended. Successful payments: {success_count}/{total_attempts}")

        # Stop flapping
        stop_flapping.set()
        flapping_thread.join()

        # Stabilize
        print("\\n[Chaos] 🔧 Stabilizing network...")
        time.sleep(2)
        try:
            self.fiber1.connect_peer(self.fiber2)
        except:
            pass

        # Wait for channel ready
        print("[Chaos] Waiting for channel to be ready...")
        self.wait_for_channel_state(self.fiber1.get_client(), self.fiber2.get_peer_id(), "ChannelReady")

        # Verify final stability
        print("\\n[Chaos] Performing final stability check...")
        try:
            payment_hash_final = self.send_payment(self.fiber1, self.fiber2, 1000)
            self.wait_payment_state(self.fiber1, payment_hash_final, "Success")
            print("[Chaos] Stability Verified! Final payment successful. ✅")
        except Exception as e:
            assert False, f"System failed to recover from chaos: {e}"

    debug = True

    def test_proxy_network_chaos(self):
        """
        Scenario: Real Network Chaos Simulation via Proxy (Latency/Packet Loss)
        
        1. Start 2 nodes.
        2. Start a ChaosProxy pointing to Node 2's P2P port.
        3. Connect Node 1 to Node 2 VIA THE PROXY (instead of direct).
        4. Verify connection and basic payment.
        5. CHAOS: Inject high latency (e.g., 3-5 seconds).
        6. Attempt payment -> Should be slow or timeout.
        7. CHAOS: Inject packet loss.
        8. RECOVERY: Remove chaos rules.
        9. Verify network stabilizes and payments work.
        """
        # Fiber2's P2P port is usually 8230 (based on setup_method in FiberTest)
        # We need to find the actual port.
        # fiber2 is initialized with "8230" as p2p port in FiberTest.setup_method
        target_port = 8230

        # 1. Start Chaos Proxy
        print("\n[Chaos] 🌉 Starting Chaos Proxy...")
        proxy = ChaosProxy(target_host='127.0.0.1', target_port=target_port)
        proxy_port = proxy.start()

        try:
            # 2. Connect Node 1 -> Proxy -> Node 2
            # Construct peer address for Node 2 but with Proxy Port
            node2_id = self.fiber2.get_client().node_info()['addresses'][0].split('/')[-1]
            proxy_addr = f"/ip4/127.0.0.1/tcp/{proxy_port}/p2p/{node2_id}"

            print(f"[Chaos] Connecting Fiber1 to Fiber2 via Proxy ({proxy_addr})...")
            self.fiber1.get_client().connect_peer({"address": proxy_addr})

            # Wait for connection
            time.sleep(2)
            self.open_channel(self.fiber1, self.fiber2, 10000000, 10000000)

            # 3. Verify Baseline
            print("[Chaos] Verifying baseline payment...")
            payment_hash = self.send_payment(self.fiber1, self.fiber2, 1000)
            self.wait_payment_state(self.fiber1, payment_hash, "Success")
            print("[Chaos] Baseline payment successful.")

            # 4. Inject Latency
            print("\n[Chaos] 🐢 Injecting High Latency (2.0s - 3.0s)...")
            proxy.set_delay(2.0, 3.0)

            # Attempt payment - expected to be slow but might succeed if timeout is large enough
            # or fail if timeout is short.
            print("[Chaos] Attempting payment with latency...")
            start_time = time.time()
            try:
                payment_hash_slow = self.send_payment(self.fiber1, self.fiber2, 1000)
                # Wait with a longer timeout
                self.wait_payment_state(self.fiber1, payment_hash_slow, "Success", timeout=20)
                duration = time.time() - start_time
                print(f"[Chaos] Payment succeeded but took {duration:.2f}s")
            except Exception as e:
                print(f"[Chaos] Payment failed/timed out as expected: {e}")

            # 5. Inject Packet Loss
            print("\n[Chaos] 🗑️ Injecting Packet Loss (50%)...")
            proxy.set_delay(0, 0)  # Clear latency
            proxy.set_drop_rate(0.5)

            # This makes the connection very unstable
            # Ping/Pong might fail, causing disconnect
            time.sleep(5)

            # 6. Recovery
            print("\n[Chaos] 🚑 Removing Chaos (Normal Network)...")
            proxy.set_drop_rate(0)
            proxy.set_delay(0, 0)

            # Wait for stabilization (reconnection if dropped)
            time.sleep(5)
            # Ensure connected
            try:
                self.fiber1.get_client().connect_peer({"address": proxy_addr})
            except:
                pass

            print("[Chaos] Verifying recovery...")
            self.wait_for_channel_state(self.fiber1.get_client(), self.fiber2.get_peer_id(), "ChannelReady")

            payment_hash_final = self.send_payment(self.fiber1, self.fiber2, 1000)
            self.wait_payment_state(self.fiber1, payment_hash_final, "Success")
            print("[Chaos] Recovery Verified! Payment successful. ✅")

        finally:
            proxy.stop()

    def test_bbbbaass(self):
        name = 'node2'
        tox = ToxiproxyClient()

        listen_port = 18230
        # tox.create_proxy(name, "0.0.0.0", listen_port, "0.0.0.0", 8230)

        tox.update_latency(name, latency_ms=100, jitter_ms=20, direction="downstream")
        tox.update_latency(name, latency_ms=100, jitter_ms=20, direction="upstream")
        # tox.update_timeout(name, timeout_ms=500, toxicity=0.1, direction="downstream")

    def test_node_link(self):
        tox = ToxiproxyClient()
        name = 'node2'
        listen_port = 18230
        tox.create_proxy(name, "0.0.0.0", listen_port, "0.0.0.0", 8230)
        tox.add_latency(name, latency_ms=5000, jitter_ms=200, direction="downstream")
        tox.add_latency(name, latency_ms=5000, jitter_ms=200, direction="upstream")
        node2_id = self.fiber2.get_client().node_info()['addresses'][0].split('/')[-1]
        self.fiber1.get_client().connect_peer({
            'address': f"/ip4/127.0.0.1/tcp/{listen_port}/p2p/{node2_id}"
        })
        time.sleep(5)
        self.fiber1.get_client().list_peers()

    def test_get_mmss(self):
        channels = self.fiber1.get_client().list_channels({})
        # for channel in channels['channels']:

        for channel in channels['channels']:
            for tlc in channel['pending_tlcs']:
                print(f"hash:{tlc['payment_hash']}, tlc type:{tlc['status']},expiry time:{hex_timestamp_to_datetime(tlc['expiry'])}")

    def test_000222(self):
        for i in range(100):
            self.send_payment(self.fiber1, self.fiber2, 1,False,try_count=0)
        # self.open_channel(self.fiber1, self.fiber2, 1000*100000000, 100000000)
        # self.fiber1.get_client().disconnect_peer({
        #     "peer_id":"QmNwCroncyHHsiDC8MbnaZ4wp9R5L4D8HgsTqeVm5p6fHM"
        # })
        # time.sleep(1)
        self.fiber1.get_client().list_peers()
        # self.fiber2.get_client().list_peers()
        # self.fiber1.get_client().list_channels({})
        # self.fiber1.get_client().list_peers()
        # self.fiber2.get_client().list_peers()
        # self.fiber1.connect_peer(self.fiber2)

    def test_lst(self):
        # target_port = 8230
        # proxy = ChaosProxy(target_host='127.0.0.1', target_port=target_port)
        # proxy_port = proxy.start()
        self.fiber1.get_client().disconnect_peer({
            'peer_id': self.fiber2.get_peer_id()
        })
        # Construct peer address for Node 2 but with Proxy Port
        node2_id = self.fiber2.get_client().node_info()['addresses'][0].split('/')[-1]
        proxy_addr = f"/ip4/127.0.0.1/tcp/18230/p2p/{node2_id}"

        print(f"[Chaos] Connecting Fiber1 to Fiber2 via Proxy ({proxy_addr})...")
        self.fiber1.get_client().connect_peer({"address": proxy_addr})
        time.sleep(5)
        peers = self.fiber1.get_client().list_peers()
        print(peers)
        # time.sleep(100000)

    def test_0000(self):
        """
        同时压测
            fiber1 -> fiber2
            fiber1 -> fiber3
        定时返回压测延迟，每 5 秒返回一次
        """
        # self.fiber3 = self.start_new_mock_fiber("")
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 1000 * 100000000)
        self.open_channel(self.fiber1, self.fiber3, 1000 * 100000000, 1000 * 100000000)
        stop_flag = threading.Event()
        lat_12 = []
        lat_13 = []
        lock = threading.Lock()
        def worker(f_to):
            while not stop_flag.is_set():
                start = time.time()
                try:
                    h = self.send_payment(self.fiber1, f_to, 100)
                    # self.wait_payment_state(self.fiber1, h, "Success", timeout=15)
                    d = time.time() - start
                    with lock:
                        if f_to == self.fiber2:
                            lat_12.append(d)
                        else:
                            lat_13.append(d)
                except Exception:
                    pass
                time.sleep(0.2)
        def reporter():
            while not stop_flag.is_set():
                time.sleep(5)
                with lock:
                    a12 = sum(lat_12) / len(lat_12) if lat_12 else 0
                    a13 = sum(lat_13) / len(lat_13) if lat_13 else 0
                    s12 = sorted(lat_12)
                    s13 = sorted(lat_13)
                    p95_12 = s12[int(0.95 * len(s12))] if s12 else 0
                    p95_13 = s13[int(0.95 * len(s13))] if s13 else 0
                print(f"[Chaos] 5s 延迟统计: 1->2 avg={a12:.3f}s p95={p95_12:.3f}s | 1->3 avg={a13:.3f}s p95={p95_13:.3f}s")
        threads_12 = [threading.Thread(target=worker, args=(self.fiber2,)) for _ in range(15)]
        threads_13 = [threading.Thread(target=worker, args=(self.fiber3,)) for _ in range(15)]

        tr = threading.Thread(target=reporter)
        for t in threads_12: t.start()
        for t in threads_13: t.start()
        tr.start()
        time.sleep(300)
        stop_flag.set()
        for t in threads_12: t.join()
        for t in threads_13: t.join()
        tr.join()


    def test_toxiproxy_limit_8114(self):
        tox = ToxiproxyClient()
        if tox.ping() is None:
            pytest.skip("未检测到 Toxiproxy 服务，请先运行 toxiproxy-server 或 docker 版本。")
        name = "ckb_rpc_8114"
        listen_port = 18114
        try:
            try:
                tox.delete_proxy(name)
            except Exception:
                pass
            tox.create_proxy(name, "0.0.0.0", listen_port, "0.0.0.0", 8114)
            tox.add_latency(name, latency_ms=1000, jitter_ms=200, direction="downstream")
            tox.add_latency(name, latency_ms=1000, jitter_ms=200, direction="upstream")
            self.node.rpcUrl = f"http://127.0.0.1:{listen_port}"
            self.node.client = RPCClient(self.node.rpcUrl)
            tip = self.node.getClient().get_tip_block_number()
            print(f"[Chaos] Toxiproxy 生效，当前 tip: {tip}")
        finally:
            try:
                pass
                # tox.delete_proxy(name)
            except Exception:
                pass
