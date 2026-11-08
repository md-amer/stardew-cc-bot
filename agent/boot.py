"""After game start: load the agent save and pause on the game menu."""
import time, sv
for _ in range(60):
    try:
        s = sv.state()
        if s.get("title"): break
    except Exception: pass
    time.sleep(1)
time.sleep(1)
print(sv.call("load_agent_save"))
s = sv.wait(lambda s: s.get("world_ready") and s.get("free"), timeout=90, every=0.5)
sv.call("tap", key="Escape")
print("loaded", s["season"], s["day"], s["time"], s["player"]["loc"])
