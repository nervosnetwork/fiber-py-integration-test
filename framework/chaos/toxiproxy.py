import requests

class ToxiproxyClient:
    def __init__(self, host="127.0.0.1", port=8474):
        self.base = f"http://{host}:{port}"

    def _request(self, method, path, json=None):
        url = f"{self.base}{path}"
        r = requests.request(method, url, json=json, timeout=5)
        r.raise_for_status()
        return r.json() if r.content else None

    def ping(self):
        try:
            return self._request("GET", "/proxies")
        except Exception:
            return None

    def create_proxy(self, name, listen_host, listen_port, upstream_host, upstream_port):
        payload = {
            "name": name,
            "listen": f"{listen_host}:{listen_port}",
            "upstream": f"{upstream_host}:{upstream_port}",
            "enabled": True,
        }
        return self._request("POST", "/proxies", payload)

    def delete_proxy(self, name):
        return self._request("DELETE", f"/proxies/{name}")

    def add_latency(self, proxy_name, latency_ms, jitter_ms=0, toxicity=1.0, direction="downstream"):
        payload = {
            "name": f"latency_{direction}",
            "type": "latency",
            "toxicity": toxicity,
            "stream": direction,
            "attributes": {
                "latency": latency_ms,
                "jitter": jitter_ms,
            },
        }
        return self._request("POST", f"/proxies/{proxy_name}/toxics", payload)

    def add_bandwidth(self, proxy_name, rate_kbps, toxicity=1.0, direction="downstream"):
        payload = {
            "name": f"bandwidth_{direction}",
            "type": "bandwidth",
            "toxicity": toxicity,
            "stream": direction,
            "attributes": {
                "rate": rate_kbps,
            },
        }
        return self._request("POST", f"/proxies/{proxy_name}/toxics", payload)

    def list_toxics(self, proxy_name):
        return self._request("GET", f"/proxies/{proxy_name}/toxics")

    def update_latency(self, proxy_name, latency_ms, jitter_ms=0, direction="downstream", toxicity=None, toxic_name=None):
        name = toxic_name or f"latency_{direction}"
        payload = {
            "attributes": {
                "latency": latency_ms,
                "jitter": jitter_ms,
            }
        }
        if toxicity is not None:
            payload["toxicity"] = toxicity
        return self._request("POST", f"/proxies/{proxy_name}/toxics/{name}", payload)

    def remove_toxic(self, proxy_name, toxic_name):
        return self._request("DELETE", f"/proxies/{proxy_name}/toxics/{toxic_name}")

    def add_timeout(self, proxy_name, timeout_ms, toxicity=1.0, direction="downstream"):
        payload = {
            "name": f"timeout_{direction}",
            "type": "timeout",
            "toxicity": toxicity,
            "stream": direction,
            "attributes": {
                "timeout": timeout_ms,
            },
        }
        return self._request("POST", f"/proxies/{proxy_name}/toxics", payload)

    def update_timeout(self, proxy_name, timeout_ms, direction="downstream", toxicity=None, toxic_name=None):
        name = toxic_name or f"timeout_{direction}"
        payload = {
            "attributes": {
                "timeout": timeout_ms,
            }
        }
        if toxicity is not None:
            payload["toxicity"] = toxicity
        return self._request("POST", f"/proxies/{proxy_name}/toxics/{name}", payload)
 
    def add_loss(self, proxy_name, loss_rate, timeout_ms=50, direction="downstream"):
        payload = {
            "name": f"loss_{direction}",
            "type": "timeout",
            "toxicity": float(loss_rate),
            "stream": direction,
            "attributes": {
                "timeout": timeout_ms,
            },
        }
        return self._request("POST", f"/proxies/{proxy_name}/toxics", payload)
 
    def update_loss(self, proxy_name, loss_rate, timeout_ms=50, direction="downstream", toxic_name=None):
        name = toxic_name or f"loss_{direction}"
        payload = {
            "attributes": {
                "timeout": timeout_ms,
            },
            "toxicity": float(loss_rate),
        }
        return self._request("POST", f"/proxies/{proxy_name}/toxics/{name}", payload)
