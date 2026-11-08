"""Thin client for the ClaudeHands mod (http://127.0.0.1:8775)."""
import json, time, urllib.request

URL = "http://127.0.0.1:8775/"

SPEED = [1]       # last speed seen (fast-forward factor): waits shrink with it

def call(cmd, **kw):
    kw["cmd"] = cmd
    req = urllib.request.Request(URL, data=json.dumps(kw).encode(), method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        res = json.loads(r.read())
    if not res.get("ok"):
        raise RuntimeError(f"{cmd}: {res.get('error')}")
    d = res.get("data")
    if cmd == "speed" and isinstance(d, dict) and d.get("speed"):
        # headless turbo: the real game-time factor is the measured one, not the requested update count
        SPEED[0] = 1 if int(d["speed"]) <= 1 else (max(1.0, float(d.get("turbo") or d.get("effective") or 1)) if d.get("headless") else int(d["speed"]))
    return d

# flavored artisan goods are named "Melon Jelly", "Blueberry Wine"...; bundles ask for the base item (by id)
BASE_BY_ID = {"(O)344": "Jelly", "(O)348": "Wine", "(O)342": "Pickles", "(O)350": "Juice", "(O)340": "Honey", "(O)447": "Aged Roe", "(O)812": "Roe"}

def state():
    s = call("state")
    for i in s.get("inventory") or []:
        b = BASE_BY_ID.get(i.get("id"))
        if b: i["name"] = b
    for g in (s.get("menu") or {}).get("grab") or []:        # chest list has no ids: name rule
        g["name"] = base_name(g["name"])
    return s

_NOT_JELLY = {"River Jelly", "Sea Jelly", "Cave Jelly"}

def base_name(n):
    if n.endswith(" Jelly") and n not in _NOT_JELLY: return "Jelly"
    for suf in (" Wine", " Pickles", " Juice"):
        if n.endswith(suf): return suf.strip()
    if n.endswith(" Honey") and n != "Wild Honey": return "Honey"
    return n
def widgets(): return call("widgets")

def click_widget(field=None, name=None, i=None, right=False):
    w = widgets()
    for x in w["widgets"]:
        if (field is None or x["field"] == field) and (name is None or x["name"] == name) and (i is None or x["i"] == i):
            call("click", x=x["x"], y=x["y"], right=right)
            time.sleep(0.15)
            return x
    raise LookupError(f"widget field={field} name={name} i={i} not in {w['menu']}")

def wait(pred, timeout=30, every=0.1):
    # W8/W15: at 12x a game night is ~30 s real; a fixed 10-180 s wait let the farmer pass out. Game-driven waits
    # are scaled by the fast-forward factor (everything in the game, menus included, runs that much faster).
    # session 6: turbo is requested for the wait, so game time per real second is known; the old 3 s floor
    # = 2+ game hours at ~40x (Su 3-5 Y2 lost the afternoon to one failed warp wait)
    timeout = max(0.5, timeout * 2.0 / SPEED[0]) if SPEED[0] > 1 else timeout
    # session 6: the mod idles at 1x unless asked; a wait is "let the game run until pred", so ask for turbo
    # (Su 3 Y2: holding a move key at 1x vs a timeout shrunk for turbo -> mining step failed, day ended 9:10)
    if SPEED[0] > 1: call("turbo", sec=timeout + 1)
    t = time.time()
    try:
        while time.time() - t < timeout:
            s = state()
            if pred(s): return s
            time.sleep(every)
    finally:
        if SPEED[0] > 1: call("turbo", sec=0)
    raise TimeoutError("wait timed out")


def wait_clock(t, max_real=60):
    """Let game time run (turbo) until the clock reads t. Session 6: idle waits at 1x took real hours."""
    t0 = time.time()
    while time.time() - t0 < max_real:
        if state()["time"] >= t: return True
        call("turbo", sec=3, until=t); time.sleep(0.3)
    return state()["time"] >= t
