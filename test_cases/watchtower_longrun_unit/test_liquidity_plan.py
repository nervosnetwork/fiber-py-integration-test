"""No-devnet unit check of auto-open direction for the testnet C-C-P-P-C-C layout."""
from watchtower_longrun.builder.scenario_builder import liquidity_plan
from watchtower_longrun.common import Topology


def _topo():
    ctl = {"N1": 1, "N2": 1, "N3": 0, "N4": 0, "N5": 1, "N6": 1}
    return Topology({"ckb_rpc_url": "x", "nodes": [{"name": n, "controlled": bool(c)} for n, c in ctl.items()]})


def test_plan_with_open_from_downstream():
    assert liquidity_plan(_topo(), {"open_from_downstream": True}) == {
        "N1-N2": "open_upstream", "N2-N3": "open_upstream", "N3-N4": "fail",
        "N4-N5": "open_downstream", "N5-N6": "open_upstream"}


def test_plan_without_open_from_downstream():
    p = liquidity_plan(_topo(), {})
    assert p["N4-N5"] == "fail" and p["N3-N4"] == "fail" and p["N2-N3"] == "open_upstream"
