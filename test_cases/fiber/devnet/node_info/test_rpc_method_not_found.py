import pytest
import requests
import json

from framework.basic_fiber import FiberTest


class TestRpcMethodNotFound(FiberTest):
    """
    PR-1235: RPC method not found should not return unauthorized when auth is disabled

    When biscuit auth is disabled (local RPC mode, which is the default),
    calling a non-existent RPC method should return "Method not found" error,
    NOT "Unauthorized" error.

    Before fix: get_rule() fails for unknown method → return false → "Unauthorized" (-32999)
    After fix: get_rule() fails for unknown method → return true → "Method not found" (-32601)
    """

    def _raw_rpc_call(self, url, method, params=None):
        """Make a raw JSON-RPC call and return the full response (including error)."""
        if params is None:
            params = [{}]
        data = {"id": 42, "jsonrpc": "2.0", "method": method, "params": params}
        headers = {"content-type": "application/json"}
        response = requests.post(url, data=json.dumps(data), headers=headers)
        return response.json()

    def test_nonexistent_method_should_not_return_unauthorized(self):
        """Call a non-existent RPC method; error should be 'method not found', not 'Unauthorized'."""
        url = self.fiber1.get_client().url
        response = self._raw_rpc_call(url, "nonexistent_method")

        assert "error" in response, "Expected an error response for non-existent method"
        error = response["error"]
        error_message = error.get("message", "")
        error_code = error.get("code", 0)

        # Should NOT be Unauthorized (-32999)
        assert error_code != -32999, (
            f"Non-existent method returned 'Unauthorized' (code -32999). "
            f"PR #1235 fix not applied. Got: {error}"
        )
        assert "Unauthorized" not in error_message, (
            f"Non-existent method returned 'Unauthorized' message. "
            f"PR #1235 fix not applied. Got: {error}"
        )

        # Should be Method not found (-32601) from JSON-RPC layer
        assert error_code == -32601, (
            f"Expected 'Method not found' error code -32601, got code {error_code}: {error}"
        )

    def test_existing_method_still_works_without_auth(self):
        """Ensure existing RPC methods still work normally when auth is disabled."""
        result = self.fiber1.get_client().node_info()
        assert result is not None
        assert "pubkey" in result

    def test_multiple_nonexistent_methods(self):
        """Various non-existent method names should all return 'method not found'."""
        url = self.fiber1.get_client().url
        fake_methods = [
            "fake_method",
            "get_nonexistent",
            "open_channel_v2",
            "some_random_rpc",
        ]
        for method in fake_methods:
            response = self._raw_rpc_call(url, method)
            assert "error" in response, f"Expected error for method '{method}'"
            error = response["error"]
            assert error.get("code") == -32601, (
                f"Method '{method}' returned unexpected error code {error.get('code')}: {error}"
            )
            assert error.get("code") != -32999, (
                f"Method '{method}' returned Unauthorized. PR #1235 fix not applied."
            )
