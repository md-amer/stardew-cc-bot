"""Festival days (wiki: Festivals). Shops/homes locked; time stops inside; leaving -> Farm at 22:00."""
import time
import sv, act, town, farming, calendar_sv

def in_festival():
    return str(sv.state().get("event") or "").startswith("festival")

def enter(loc):
    """The festival map replaces the target map on arrival; stop routing as soon as the festival runs."""
    if in_festival():
        return
    try:
        act.goto(loc)
    except Exception as e:
        if not in_festival():
            raise
        act.log(f"festival entered mid-route ({e!r})")
    for _ in range(200):
        s = act.dismiss()
        if s.get("free"): break
        time.sleep(0.3)

def talk(npc_name):
    a = sv.call("around", r=40)
    n = next((n for n in a["npcs"] if n["name"] == npc_name), None)
    if not n:
        act.log(f"festival: {npc_name} not found"); return False
    act.walk(n["x"], n["y"], adjacent=True)
    act.use(n["x"], n["y"], right=True)
    time.sleep(0.6)
    return True

def socialize(skip=("Lewis",)):
    """Festival clock is frozen: talking to every villager costs no game time (friendship for Perfection).
    Lewis is skipped: talking to him starts the main event."""
    talked = []
    for _ in range(60):
        a = sv.call("around", r=80)
        _, me = act.here()
        left = [n for n in a["npcs"] if not n["monster"] and n["name"] not in skip and n["name"] not in talked]
        if not left:
            break
        n = min(left, key=lambda n: abs(n["x"] - me[0]) + abs(n["y"] - me[1]))
        talked.append(n["name"])
        if act.walk(n["x"], n["y"], adjacent=True, timeout=20) != "arrived":
            continue
        act.use(n["x"], n["y"], right=True)
        time.sleep(0.4)
        act.dismiss(20)
    act.log(f"festival: talked to {len(talked)} villagers")
    return talked

def open_festival_shop():
    """Festival booths are map tiles with Action "Shop <id>" (decompiled Event.checkAction), not NPC talk."""
    acts = [a for a in sv.call("actions") if a["action"].split(" ")[0] in ("Shop", "OpenShop")]
    act.log(f"festival shop tiles: {acts[:4]}")
    for a in acts:
        act.walk(a["x"], a["y"], adjacent=True)
        act.use(a["x"], a["y"], right=True)
        try:
            sv.wait(lambda s: (s.get("menu") or {}).get("type") == "ShopMenu", timeout=4)
            time.sleep(0.6)                 # ShopMenu safetyTimer
            return True
        except TimeoutError:
            act.dismiss()
    act.log("festival: no shop opened")
    return False

def leave(entry_tile=None):
    """Walk off the festival map at the entry edge; the game asks (ConfirmationDialog, OK) -> Farm at 22:00."""
    s = sv.state(); loc0 = s["player"]["loc"]; keys = s["keys"]
    if entry_tile:
        act.walk(*entry_tile)
    for k in (keys["left"], keys["down"], keys["right"], keys["up"]):
        sv.call("hold", down=[k])
        t0 = time.time()
        while time.time() - t0 < 6 and not sv.state().get("menu"):
            time.sleep(0.2)
        sv.call("hold", up=[k])
        w = sv.widgets()["widgets"]
        ok = [x for x in w if x["field"] == "okButton"] or [x for x in w if x["field"] == "responseCC"]
        if ok:
            sv.call("click", x=ok[0]["x"], y=ok[0]["y"]); break
    sv.wait(lambda s: s["player"]["loc"] != loc0, timeout=30)
    for _ in range(100):
        s = act.dismiss()
        if s.get("free"): break
        time.sleep(0.3)

def egg_festival(seed_budget_keep=50):
    s = sv.state()
    while sv.state()["time"] < 900:
        sv.call("turbo", sec=5, until=900); time.sleep(1)
    enter("Town")
    entry = tuple(sv.state()["player"]["tile"])      # leave the way we came in
    try:
        socialize()
    except Exception as e:
        act.log(f"festival socialize failed: {e!r}")
    if open_festival_shop():
        money = sv.state()["player"]["money"]
        n = max(0, (money - seed_budget_keep) // 100)
        if n:
            town._last_shop = None
            town.buy({"Strawberry Seeds": n})
        town.close_menu()
    leave(entry)
    act.goto("Farm")
    act.log(f"strawberries planted: {farming.replant('Strawberry Seeds')}")
