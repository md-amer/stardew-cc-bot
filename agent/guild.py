"""Adventurer's Guild (wiki: open 2pm-2am; Femur 350g after floor 10, Iron Dirk 500g after 15,
Steel Smallsword / Silver Saber 750g after 20). Buy the best affordable weapon, park the old one."""
import time
import sv, act, town, mining

# wiki damage ranges; best first
WEAPONS = [("Galaxy Sword", 50000, 999, (60, 80)), ("Silver Saber", 750, 20, (8, 15)), ("Steel Smallsword", 750, 20, (4, 8)),
           ("Femur", 350, 10, (6, 11)), ("Wooden Blade", 250, 0, (3, 7)), ("Rusty Sword", 250, 0, (2, 5))]

def owned():
    names = {i["name"] for i in act.inv()}
    return next((w for w in WEAPONS if w[0] in names), None)

def visit(reserve=500):
    s = sv.state()
    if s["time"] < 1400 or s["time"] >= 2300:
        return
    cur = owned()
    money = s["player"]["money"] - reserve
    deepest = mining.deepest_lift()
    best = next((w for w in WEAPONS if w[2] <= deepest and w[1] <= money), None)
    if not best or (cur and WEAPONS.index(best) >= WEAPONS.index(cur)):
        return
    act.log(f"guild: want {best[0]} ({best[1]}g, dmg {best[3]}) over {cur and cur[0]}")
    act.goto("AdventureGuild")
    for _ in range(100):                      # first visit: Marlon's quest cutscene
        st = act.dismiss()
        if st.get("free") and not st.get("event"): break
        time.sleep(0.3)
    acts = sv.call("actions")
    act.log(f"guild actions: {[a['action'] for a in acts][:8]}")
    shop = next((a for a in acts if "Shop" in a["action"] or "Adventure" in a["action"]), None)
    if not shop:
        act.log("guild: no shop tile"); return
    act.walk(shop["x"], shop["y"], adjacent=True)
    act.use(shop["x"], shop["y"], right=True)
    time.sleep(0.8)
    resp = [w for w in sv.widgets()["widgets"] if w["field"] == "responseCC"]
    if resp:                                   # "Need something?" [Shop, ..., Leave] (Fa 9)
        sv.call("click", x=resp[0]["x"], y=resp[0]["y"]); time.sleep(0.8)
    try:
        sv.wait(lambda s: (s.get("menu") or {}).get("type") == "ShopMenu", timeout=5)
    except TimeoutError:
        act.log(f"guild: shop did not open (menu {sv.state().get('menu')})"); act.dismiss(); town.close_menu(); return
    time.sleep(0.6)
    town._last_shop = None
    town.buy({best[0]: 1})
    town.close_menu()
    act.log(f"guild: now carrying {owned() and owned()[0]}")
