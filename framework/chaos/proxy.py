import socket
import threading
import time
import random
import select

class ChaosProxy:
    """
    A TCP Proxy that can inject network faults (latency, packet loss).
    """
    def __init__(self, target_host, target_port, proxy_port=0):
        self.target_host = target_host
        self.target_port = int(target_port)
        self.proxy_port = int(proxy_port)
        self.server_socket = None
        self.listening = False
        self.threads = []
        
        # Chaos parameters
        self.delay_min = 0.0
        self.delay_max = 0.0
        self.drop_rate = 0.0 # 0.0 to 1.0
        self.lock = threading.Lock()

    def start(self):
        """Starts the proxy server."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', self.proxy_port))
        if self.proxy_port == 0:
            self.proxy_port = self.server_socket.getsockname()[1]
        self.server_socket.listen(10)
        self.listening = True
        
        t = threading.Thread(target=self._accept_loop, name="ChaosProxy-Acceptor")
        t.daemon = True
        t.start()
        self.threads.append(t)
        print(f"[ChaosProxy] Started on port {self.proxy_port} -> {self.target_host}:{self.target_port}")
        return self.proxy_port

    def stop(self):
        """Stops the proxy server."""
        self.listening = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        print("[ChaosProxy] Stopped.")

    def set_delay(self, min_delay, max_delay):
        """Sets the latency range in seconds."""
        with self.lock:
            self.delay_min = min_delay
            self.delay_max = max_delay
            if max_delay > 0:
                print(f"[ChaosProxy] Latency set to {min_delay}-{max_delay}s")
            else:
                print(f"[ChaosProxy] Latency cleared")

    def set_drop_rate(self, rate):
        """Sets the packet drop rate (0.0 to 1.0)."""
        with self.lock:
            self.drop_rate = rate
            if rate > 0:
                print(f"[ChaosProxy] Packet drop rate set to {rate*100}%")
            else:
                print(f"[ChaosProxy] Packet drop cleared")

    def _accept_loop(self):
        while self.listening:
            try:
                # Use select to handle non-blocking accept or timeout
                if not self.server_socket:
                    break
                readable, _, _ = select.select([self.server_socket], [], [], 1.0)
                if self.server_socket in readable:
                    client_sock, addr = self.server_socket.accept()
                    self._handle_client(client_sock)
            except OSError:
                break # Socket closed
            except Exception as e:
                if self.listening:
                    print(f"[ChaosProxy] Accept error: {e}")

    def _handle_client(self, client_sock):
        try:
            target_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_sock.connect((self.target_host, self.target_port))
            
            # Start two threads for bidirectional forwarding
            t1 = threading.Thread(target=self._forward, args=(client_sock, target_sock, "Client->Target"))
            t2 = threading.Thread(target=self._forward, args=(target_sock, client_sock, "Target->Client"))
            t1.daemon = True
            t2.daemon = True
            t1.start()
            t2.start()
        except Exception as e:
            # print(f"[ChaosProxy] Connection failed: {e}")
            client_sock.close()

    def _forward(self, source, destination, direction):
        try:
            while self.listening:
                data = source.recv(4096)
                if not data:
                    break
                
                # Apply Chaos
                with self.lock:
                    drop = self.drop_rate
                    d_min = self.delay_min
                    d_max = self.delay_max
                
                if drop > 0 and random.random() < drop:
                    # print(f"[{direction}] Dropped {len(data)} bytes")
                    continue
                
                if d_max > 0:
                    delay = random.uniform(d_min, d_max)
                    time.sleep(delay)
                    
                destination.sendall(data)
        except Exception:
            pass
        finally:
            try:
                source.close()
            except: pass
            try:
                destination.close()
            except: pass
