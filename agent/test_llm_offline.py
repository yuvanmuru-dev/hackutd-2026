"""Router test: a self-hosted fast model is tried first and the hosted API takes over when it's down.
Run: python test_llm_offline.py (prints PASS). No network: endpoints are fakes."""
import os

os.environ.update(NVIDIA_API_KEY="test", NEMOTRON_NANO_BASE_URL="http://brev-box:8000/v1", NEMOTRON_NANO_SELF_MODEL="nvidia/self-nano",
                  DEMO_MODE="0", LLM_CACHE="off")

from core import llm  # noqa: E402


class _Resp:
    def __init__(self, text):
        self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]


class Fake:
    def __init__(self, name, fail=False):
        self.name, self.fail, self.models = name, fail, []
        self.chat = type("Ch", (), {"completions": self})()

    def create(self, model, messages, **kw):
        self.models.append(model)
        if self.fail:
            raise ConnectionError("box stopped")
        return _Resp(f"answer from {self.name}")


selfbox, hosted = Fake("self"), Fake("hosted")
llm._client_for = lambda base, key: selfbox if "brev-box" in base else hosted

text, model = llm.chat("nano", [{"role": "user", "content": "hi"}])
assert text == "answer from self" and model == "nvidia/self-nano", (text, model)

selfbox.fail = True                                   # box goes down
text, model = llm.chat("nano", [{"role": "user", "content": "hi"}])
assert text == "answer from hosted" and model == llm.model_for("nano"), (text, model)
n = len(selfbox.models)
llm.chat("nano", [{"role": "user", "content": "hi"}])   # skipped for 60 s, no extra delay
assert len(selfbox.models) == n, "a down box should be skipped"

text, model = llm.chat("super", [{"role": "user", "content": "hi"}])   # Ultra stays hosted
assert text == "answer from hosted" and model == llm.model_for("super")
assert [t["where"] for t in llm.targets("nano")] == ["self-hosted", "hosted"] and [t["where"] for t in llm.targets("super")] == ["hosted"]
print("PASS")
