import os
import time

from framework.basic import CkbTest
from framework.fiber_rpc import FiberRPCClient
from framework.rpc import RPCClient
from framework.test_fiber import Fiber, FiberConfigPath
from framework.util import generate_random_preimage
import logging

LOGGER = logging.getLogger(__name__)

# ckb1qzda0cr08m85hc8jlnfp3zer7xulejywt49kt2rr0vthywaa50xwsqtlpgc29k57ufndd7gpm2jjvpwc2hqygjgtf54lg
# ckb1qzda0cr08m85hc8jlnfp3zer7xulejywt49kt2rr0vthywaa50xwsq0z6h6nlju0mcdp0ny0sx77tmu6j2700lqkdeakp
class TestFiber(CkbTest):
    cryptapeFiber1_peer_address = (
        "/ip4/52.52.69.223/tcp/8228/p2p/QmZCfzENZqWrWwifJj9BFDvxQWFyYw5GjdB4vN7Ynd4FxY"
    )
    cryptapeFiber1_peer_id = "QmZCfzENZqWrWwifJj9BFDvxQWFyYw5GjdB4vN7Ynd4FxY"

    cryptapeFiber2_peer_address = (
        "/ip4/54.178.252.1/tcp/8228/p2p/QmZ73KHvZ5GFxf6XhHZ3icPeKFo93rk86kZ8qauox3avJP"
    )
    cryptapeFiber2_peer_id = "QmZ73KHvZ5GFxf6XhHZ3icPeKFo93rk86kZ8qauox3avJP"

    ACCOUNT_PRIVATE_1 = os.getenv("ACCOUNT_PRIVATE_1")
    ACCOUNT_PRIVATE_2 = os.getenv("ACCOUNT_PRIVATE_2")

    fiber1: Fiber
    fiber2: Fiber


    def test_account_msg(self):
        ACCOUNT_PRIVATE_1 = "0x1ae4515b745efcd6f00c1b40aaeef3dd66c82d75f8f43d0f18e1a1eecb90ada4"
        ACCOUNT_PRIVATE_2 = "0x218d76bbfe5ffe3a8ef3ad486e784ec333749575fb3c697126cdaa8084d42532"
        self.Ckb_cli.util_key_info_by_private_key(ACCOUNT_PRIVATE_1)
        self.Ckb_cli.util_key_info_by_private_key(ACCOUNT_PRIVATE_2)

