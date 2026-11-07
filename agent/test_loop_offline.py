"""Offline test of the agent loop with a fake model. No API key or network needed.

Run: python test_loop_offline.py   (should print PASS)
"""
import json
from types import SimpleNamespace as NS

import nemotron_agent as ag

calls = []
ag.TOOLS["geocode_address"] = lambda address: (calls.append("geo"), {"found": True, "lat": 32.98, "lon": -96.75, "source": "fake"})[1]
ag.TOOLS["flood_zone"] = lambda lat, lon: (calls.append("flood"), {"mapped": True, "flood_zone": "X", "special_flood_hazard_area": False, "source": "fake"})[1]


class ToolCall:
    def __init__(self, id, name, args):
        self.id = id
        self.function = NS(name=name, arguments=json.dumps(args))

    def model_dump(self):
        return {"id": self.id, "type": "function", "function": {"name": self.function.name, "arguments": self.function.arguments}}


script = [
    NS(content="", tool_calls=[ToolCall("1", "geocode_address", {"address": "x"})]),
    NS(content="", tool_calls=[ToolCall("2", "flood_zone", {"lat": 32.98, "lon": -96.75})]),
    NS(content='Here you go: {"address":"x","claims":[{"claim":"not in flood zone","verdict":"supported","evidence":"Zone X","source":"fake"}],"trust_score":90,"summary":"ok"}', tool_calls=None),
]


class FakeClient:
    def __init__(self):
        self.chat = NS(completions=NS(create=self.create))
        self.i = 0

    def create(self, **kw):
        assert kw["tools"], "tools must be passed"
        m = script[self.i]
        self.i += 1
        return NS(choices=[NS(message=m)])


report = ag.run_agent(FakeClient(), "x", "Not in a flood zone.", on_step=lambda s: None)
assert calls == ["geo", "flood"], calls
assert report["claims"][0]["verdict"] == "supported", report
assert ag.run_tool("nope", "{}")["error"].startswith("unknown tool")
print("PASS")
