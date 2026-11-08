"""Coop + chickens for the Animal bundle (Large Egg white + brown) and Y2 speed.

Wiki facts used (wiki.py): Coop = 4,000g + 300 Wood + 100 Stone at Robin, 3 days to build, 6x3 tiles, holds 4.
Chicken 800g at Marnie (white or brown at random). Marnie's shop 9:00-16:00, closed Mon/Tue.
Robin's shop 9:00-17:00, closed Tuesday. Without a Silo the hopper is empty: hay goes onto the feeding bench by hand.

Menus are driven by clicks only (mod endpoints `carpenter`, `build_spots`, `animal_menu` read what is drawn).
"""
import time
import sv, act, town

COOP_COST, COOP_WOOD, COOP_STONE = 4000, 300, 100
CHICKEN = 800
# wiki (Coop / Barn / Chicken / Cow): cost, materials, footprint, animal price; Barn 3 days like the Coop
SPEC = {"Coop": dict(cost=4000, wood=300, stone=100, w=6, h=3, animal="Chicken", price=800, key="coop", count="chickens",
                     n=3, wants={"Large Egg"}, cx=56, cy=12, tag="Hen"),
        # wiki Silo: 100g + 100 Stone + 10 Clay + 5 Copper Bars; hay bought or added goes to the silo and the hoppers
        # feed the animals (W24-28: hens crowd the bench, so hand-feeding failed for days)
        "Silo": dict(cost=100, wood=0, stone=100, extra={"Clay": 10, "Copper Bar": 5}, w=3, h=3, animal=None, price=0,
                     key="silo", count="silos", n=0, wants=set(), cx=58, cy=18, tag=""),
        # upgrades (wiki Coop/Barn tables; Duck 1,200g, Goat 4,000g, Pig 16,000g): CarpenterMenu "Upgrade" = click the building
        "Big Coop": dict(cost=10000, wood=400, stone=150, w=6, h=3, animal="Duck", price=1200, key="big_coop", count="ducks",
                         n=1, wants={"Duck Egg", "Duck Feather", "Rabbit's Foot"}, animal_wants={"Duck Egg", "Duck Feather"},
                         upgrade_of="Coop", tag="Duck"),
        # wiki Coop: Deluxe Coop 20,000g + Wood 500 + Stone 200, upgrade from Big Coop (2 days); wiki Rabbit: 8,000g at
        # Marnie, matures after 6 nights, Rabbit's Foot with enough friendship + happiness (Enchanter's, W27 Y2)
        "Deluxe Coop": dict(cost=20000, wood=500, stone=200, w=6, h=3, animal="Rabbit", price=8000, key="deluxe_coop",
                            count="rabbits", n=1, wants={"Rabbit's Foot"}, upgrade_of="Big Coop", tag="Rabbit"),
        "Big Barn": dict(cost=12000, wood=450, stone=200, w=7, h=4, animal="Goat", price=4000, key="big_barn", count="goats",
                         n=1, wants={"L. Goat Milk", "Truffle"}, animal_wants={"L. Goat Milk"}, upgrade_of="Barn", tag="Goat"),
        "Deluxe Barn": dict(cost=25000, wood=550, stone=300, w=7, h=4, animal="Pig", price=16000, key="deluxe_barn", count="pigs",
                            n=1, wants={"Truffle"}, animal_wants={"Truffle"}, upgrade_of="Big Barn", tag="Pig"),
        # wiki Sheep: lives in a Deluxe Barn, 8,000g at Marnie; Shears 1,000g (Marnie) to collect Wool
        "Sheep": dict(cost=0, wood=0, stone=0, w=7, h=4, animal="Sheep", price=8000, key="deluxe_barn", count="sheep",
                      n=1, wants={"Wool"}, house="Deluxe Barn", tag="Sheep"),
        "Barn": dict(cost=6000, wood=350, stone=150, w=7, h=4, animal="Cow", price=1500, key="barn", count="cows",
                     n=1, wants={"Large Milk"}, cx=46, cy=12, tag="Cow")}

def _prog():
    import play_day; return play_day.prog()

def _save(p):
    import play_day; play_day.save_prog(p)

def _abs_day(s):
    return (s["year"] - 1) * 112 + ["spring", "summer", "fall", "winter"].index(s["season"]) * 28 + s["day"]

def marnie_closed_holiday(s):
    """wiki Marnie's Ranch: shop also closed Fall 18, Winter 18, Spring 17 (bus repaired); Mon/Tue checked by caller."""
    return (s["season"], s["day"]) in (("fall", 18), ("winter", 18), ("spring", 17))

def _have(name):
    return sum(i["stack"] for i in act.inv() if i["name"] == name)

def _pick_response(want_menu, check, order):
    """Robin/Marnie counters ask a question whose options differ by game state: try options in `order`
    (indexes, negative from the end) until the wanted menu opens."""
    for idx in order:
        resp = [w for w in sv.widgets()["widgets"] if w["field"] == "responseCC"]
        if not resp:
            return False
        if -len(resp) <= idx < len(resp):
            sv.call("click", x=resp[idx]["x"], y=resp[idx]["y"]); time.sleep(1.2)
        if check():
            return True
        town.close_menu(); act.dismiss()
        return False
    return False

def _wait_open(t_open=900):
    """Winter mornings end early (no crops): walk to the shop and wait for opening, like a player."""
    for _ in range(200):
        if sv.state()["time"] >= t_open: return True
        sv.call("turbo", sec=5, until=t_open)      # LESSONS 120: game idles at 1x unless asked to skip ahead
        time.sleep(0.5)
    return sv.state()["time"] >= t_open

def want(kind="Coop"):
    import needs
    B = SPEC[kind]; q = needs.quota(); p = _prog()
    if kind == "Silo": return bool(p.get("chickens") or p.get("cows")) and not p.get("silo")
    if B.get("upgrade_of"):
        base = SPEC[B["upgrade_of"]]["key"]
        return bool(p.get(base)) and coop_ready(B["upgrade_of"]) and not p.get(B["key"]) and bool(B["wants"] & set(q))
    if kind == "Barn" and not p.get("coop"): return False          # coop first
    return bool(B["wants"] & set(q)) and not p.get(B["key"])

def want_coop():
    return want("Coop")

def build_coop():
    return build("Coop")

def build_barn():
    return build("Barn")

def build_silo():
    return build("Silo")

def upgrades():
    # Truffle first: pigs find truffles only outdoors spring-fall and a bought pig must grow up; ducks work in winter
    import needs
    truffle_chain = "Truffle" in set(needs.quota()) and not _prog().get("deluxe_barn")
    for k in ("Big Barn", "Deluxe Barn", "Big Coop", "Deluxe Coop"):
        if k in ("Big Coop", "Deluxe Coop") and truffle_chain: continue     # Robin builds one at a time; Deluxe money comes first
        if want(k):
            build(k); return

def buy_upgrade_animals():
    for k in ("Big Coop", "Deluxe Coop", "Big Barn", "Deluxe Barn", "Sheep"):
        buy_animals(k)

def build(kind="Coop"):
    B = SPEC[kind]
    COOP_COST, COOP_WOOD, COOP_STONE, CHICKEN = B["cost"], B["wood"], B["stone"], B["price"]
    s = sv.state(); p = _prog()
    if not want(kind): return
    if not (700 <= s["time"] < 1500) or (s["day"] - 1) % 7 == 1: return       # Robin closed Tuesday
    # upgrades: the building only (its animal is bought later when money allows); new houses keep 2 animals' worth
    if s["player"]["money"] < COOP_COST + (0 if B.get("upgrade_of") else 2 * CHICKEN) + 1500: return
    import donate, projects
    site = p.get(B["key"] + "_site")
    if B.get("upgrade_of"):               # click inside the existing building
        bt = p[SPEC[B["upgrade_of"]]["key"]]["tile"]
        site = {"x": bt[0] + 1, "y": bt[1] + 1}
    if not site:
        act.goto("Farm", 64, 20)
        plans = sv.call("build_plan", w=B["w"], h=B["h"], cx=B["cx"], cy=B["cy"]) or []
        if not plans:
            act.log("coop: no site on the farm (even after clearing debris)"); return
        site = plans[0]
        act.log(f"coop: site {site['x'], site['y']}, clearing {len(site['clear'])} tiles {[c['what'] for c in site['clear']][:12]}")
        tool = {"Weeds": "Scythe", "Grass": "Scythe", "Stone": "Pickaxe", "Twig": "Axe", "HoeDirt": "Pickaxe"}
        for c in site["clear"]:
            t = tool.get(c["what"], "Scythe")
            if "Weeds" in c["what"]: t = "Scythe"
            if act.walk(c["x"], c["y"], adjacent=True) != "arrived": continue
            for _ in range(3):
                act.use(c["x"], c["y"], tool=t)
                objs, feats, _ = __import__("farming").tile_info(r=2)
                if (c["x"], c["y"]) not in objs and (c["x"], c["y"]) not in feats: break
        again = [q for q in (sv.call("build_plan", w=B["w"], h=B["h"], cx=site["x"], cy=site["y"]) or []) if q["x"] == site["x"] and q["y"] == site["y"]]
        if again and again[0]["blockers"]:
            act.log(f"coop: site still blocked {again[0]['clear'][:6]}"); return
        p = _prog(); p[B["key"] + "_site"] = {"x": site["x"], "y": site["y"]}; _save(p); site = p[B["key"] + "_site"]
    extra = B.get("extra", {})
    if _have("Stone") < COOP_STONE or _have("Wood") < COOP_WOOD or any(_have(k) < v for k, v in extra.items()):
        donate.withdraw_bundle_items({"Stone", "Wood"} | set(extra))
    if any(_have(k) < v for k, v in extra.items()):
        act.log(f"{kind}: missing {[(k, _have(k)) for k, v in extra.items() if _have(k) < v]}"); return
    if sv.state()["time"] < 900:          # W6: the house door is locked before 9:00 (warp timed out)
        act.goto("Mountain"); _wait_open(900)
    act.goto("ScienceHouse")
    c = projects.counter("Carpenter", "Robin")
    if not c: act.log("coop: no Carpenter tile"); return
    need_wood = COOP_WOOD - _have("Wood")
    need_stone = COOP_STONE - _have("Stone")
    # wiki Carpenter's Shop: Year 1 Wood 10g / Stone 20g; Year 2+ Wood 50g / Stone 100g (Fa 3 Y2: 17,500g spent).
    # Year 2+: never buy Stone (mines give it free); Wood only when short by < 100
    if s["year"] >= 2:
        # small top-up is fine when rich (Fa 17 Y2: Deluxe Barn 43 short with 51k; Truffle is season-critical)
        if need_stone > 60 or (need_stone > 0 and s["player"]["money"] < COOP_COST + need_stone * 100 + 15000):
            act.log(f"{kind}: stone {_have('Stone')}/{COOP_STONE}; mine more (Robin 100g each in Y2)"); return
        if need_wood > 100:
            act.log(f"{kind}: wood {_have('Wood')}/{COOP_WOOD}; chop more (Robin 50g each in Y2)"); return
    if need_wood > 0 or need_stone > 0:
        pw, ps = (10, 20) if s["year"] == 1 else (50, 100)
        if s["player"]["money"] < COOP_COST + max(0, need_wood) * pw + max(0, need_stone) * ps + 1000: return
        act.walk(c["x"], c["y"], adjacent=True); act.use(c["x"], c["y"], right=True); time.sleep(0.8)
        if _pick_response("ShopMenu", lambda: (sv.state().get("menu") or {}).get("type") == "ShopMenu", [0]):
            time.sleep(0.6); town._last_shop = None
            order = {}
            if need_wood > 0: order["Wood"] = need_wood + 5        # W11: came 2 short of 350
            if need_stone > 0: order["Stone"] = need_stone + 5
            town.buy(order); town.close_menu()
        if _have("Wood") < COOP_WOOD or _have("Stone") < COOP_STONE:
            act.log(f"{kind}: wood {_have('Wood')}/{COOP_WOOD} stone {_have('Stone')}/{COOP_STONE}"); return
    m0 = sv.state()["player"]["money"]
    act.walk(c["x"], c["y"], adjacent=True); act.use(c["x"], c["y"], right=True); time.sleep(0.8)
    is_carp = lambda: (sv.state().get("menu") or {}).get("type") == "CarpenterMenu"
    if not _pick_response("CarpenterMenu", is_carp, [-2]):
        act.use(c["x"], c["y"], right=True); time.sleep(0.8)
        if not _pick_response("CarpenterMenu", is_carp, [-3]):
            act.log("coop: construct menu did not open"); return
    time.sleep(0.8)
    cm = sv.call("carpenter")
    for _ in range(25):
        if cm and cm["id"] == kind: break
        sv.call("click", x=cm["fwd"]["x"], y=cm["fwd"]["y"]); time.sleep(0.35)
        cm = sv.call("carpenter")
    if not cm or cm["id"] != kind or not cm["can"]:
        act.log(f"coop: blueprint {cm and cm['id']} can={cm and cm['can']}"); town.close_menu(); return
    sv.call("click", x=cm["ok"]["x"], y=cm["ok"]["y"])
    for _ in range(30):
        time.sleep(0.4)
        cm = sv.call("carpenter")
        if cm and cm["onFarm"] and not cm["freeze"]: break
    time.sleep(1.5)                                            # fade from black
    sp = dict(site)
    ts = sv.call("tile_screen", x=sp["x"], y=sp["y"])
    for _ in range(40):                                       # pan like a player: mouse at the screen edge
        if ts["visible"]: break
        W, H = ts["sw"], ts["sh"]
        mx = 5 if ts["sx"] < 150 else (W - 5 if ts["sx"] > W - 250 else W // 2)
        my = 5 if ts["sy"] < 150 else (H - 5 if ts["sy"] > H - 150 else H // 2)
        sv.call("mouse", x=mx, y=my); time.sleep(0.3)
        ts = sv.call("tile_screen", x=sp["x"], y=sp["y"])
    if not ts["visible"]:
        act.log(f"coop: could not pan to site {sp} ({ts})"); sv.call("click", **cm["cancel"]); time.sleep(2); town.close_menu(); return
    sv.call("mouse", x=ts["sx"], y=ts["sy"]); time.sleep(0.3)
    ts = sv.call("tile_screen", x=sp["x"], y=sp["y"])
    sv.call("click", x=ts["sx"], y=ts["sy"]); time.sleep(3.0)
    for _ in range(20):                                       # menu returns to Robin's shop after the build animation
        if sv.state()["player"]["money"] <= m0 - COOP_COST: break
        time.sleep(0.5)
    ok = sv.state()["player"]["money"] <= m0 - COOP_COST
    for _ in range(20):
        if not sv.state().get("menu"): break
        town.close_menu(); act.dismiss(); time.sleep(0.5)
    if ok:
        p = _prog(); p[B["key"]] = {"tile": [sp["x"], sp["y"]], "ordered": _abs_day(s)}; _save(p)
        act.log(f"{kind}: built at {(sp['x'], sp['y'])} (ready in 3 days), money {sv.state()['player']['money']}")
    else:
        act.log(f"coop: build click at {(sp['x'], sp['y'])} did not take (money {sv.state()['player']['money']})")

def coop_ready(kind="Coop"):
    kind = SPEC[kind].get("house", kind)
    p = _prog(); s = sv.state()
    c = p.get(SPEC[kind]["key"])
    if c and s["player"]["loc"] == "Farm":      # W10: construction slipped a day (festival); read the real building
        bl = sv.call("around", r=5).get("buildings", [])
        b = [b for b in bl if b["type"] == kind]
        if b: return not b[0]["building"]          # an upgrading coop is still usable (wiki Coop)
        if any(SPEC.get(x["type"], {}).get("upgrade_of") == kind or kind in x["type"] for x in bl):
            return True                   # already upgraded past this kind (Coop -> Big Coop)
        return False
    return bool(c) and _abs_day(s) >= c["ordered"] + 3

def buy_chickens():
    return buy_animals("Coop")

def buy_cows():
    return buy_animals("Barn")

def buy_animals(kind="Coop"):
    import needs
    B = SPEC[kind]; CHICKEN = B["price"]; n_target = B["n"]
    s = sv.state(); p = _prog()
    if kind == "Coop":     # Animal bundle wants a Large Egg AND a Large Brown Egg; colour is random (wiki Chicken)
        types = p.get("types_Coop") or []
        n_target = 4 if types and "Brown Chicken" not in types else (2 if not types else max(2, p.get("chickens", 0)))
    if not p.get(B["key"]) or not (B.get("animal_wants", B["wants"]) & set(needs.quota())): return
    if kind == "Sheep":     # Animal needs 5 of 6: one more slot can be a Large Egg (hens, cart); sheep only if 2+ left
        cc = needs.live() or {"bundles": []}
        an = next((b for b in cc["bundles"] if b["name"] == "Animal"), None)
        if not an or an["slots"] - sum(g["done"] for g in an["ingredients"]) < 2: return
    if p.get(B["count"], 0) >= n_target: return
    act.goto("Farm")
    if not coop_ready(kind): return
    have = p.get(B["count"], 0)
    if have >= n_target: return
    if not (700 <= s["time"] < 1330) or (s["day"] - 1) % 7 in (0, 1) or marnie_closed_holiday(s): return   # W21: arrived 16:50, shop shut at 16:00
    # W3 Y2: 16,977g vs pig 16,000 + 1,000 reserve blocked the Truffle chain by 23g; pig = winter buy, small reserve
    keep = 3500 if kind == "Barn" else (100 if kind in ("Deluxe Barn", "Big Coop", "Deluxe Coop") else 1000)   # Sp 4 Y3: duck missed by a few g
    if s["player"]["money"] < CHICKEN + keep: return      # keep spring seed money (+ Milk Pail)
    import projects
    if sv.state()["time"] < 900:
        act.goto("Forest"); _wait_open(900)
    act.goto("AnimalShop")
    c = projects.counter("AnimalShop", "Marnie")
    if not c: return
    bought = 0
    for _ in range(n_target - have):
        if sv.state()["player"]["money"] < CHICKEN + keep: break
        act.walk(c["x"], c["y"], adjacent=True); act.use(c["x"], c["y"], right=True); time.sleep(0.8)
        is_am = lambda: (sv.state().get("menu") or {}).get("type") == "PurchaseAnimalsMenu"
        if not _pick_response("PurchaseAnimalsMenu", is_am, [1]):
            act.log("chickens: animal menu did not open"); break
        time.sleep(0.6)
        am = sv.call("animal_menu")
        ch = next((a for a in am["animals"] if a["avail"] and B["animal"] in (a["name"] or "")), None)
        if not ch:
            act.log(f"chickens: no chicken button {[(a['name'], a['avail']) for a in am['animals']]}"); town.close_menu(); break
        m0 = sv.state()["player"]["money"]
        sv.call("click", x=ch["x"], y=ch["y"])
        for _ in range(30):
            time.sleep(0.4); am = sv.call("animal_menu")
            if am and am["onFarm"] and not am["freeze"]: break
        time.sleep(1.5)
        am = sv.call("animal_menu")
        # Sp 5 Y3: after the Deluxe Coop upgrade the house is "Deluxe Coop", so "Big Coop" never matched (no duck).
        # Coop animals fit any coop at or above their tier; barn animals any barn.
        fam = "Coop" if "Coop" in kind else ("Barn" if ("Barn" in kind or kind == "Sheep") else kind)
        h = next((h for h in am["houses"] if h["built"] and not h["full"] and fam in h["type"]), None)
        if not h:
            act.log(f"chickens: no coop on screen {am['houses']}"); town.close_menu(); break
        sv.call("click", x=h["sx"], y=h["sy"]); time.sleep(1.0)
        am = sv.call("animal_menu")
        for _try in range(4):     # Sp 10 Y3: house click did not register (camera still panning / click swallowed)
            if not am or am.get("naming") or not am.get("onFarm"): break
            time.sleep(1.0)
            am = sv.call("animal_menu")
            h2 = next((x for x in am["houses"] if x["type"] == h["type"] and x["x"] == h["x"]), h)
            sv.call("click", x=h2["sx"], y=h2["sy"] + (_try - 1) * 32); time.sleep(1.0)
            am = sv.call("animal_menu")
        # Sp 7 Y3: duck purchase ended "bought 0" with no message: log each phase
        act.log(f"{kind}: picked {ch.get('name')} at {(ch['x'], ch['y'])}, clicked house {h['type']} at {(h['sx'], h['sy'])}; "
                f"menu now naming={am and am.get('naming')} onFarm={am and am.get('onFarm')} money {sv.state()['player']['money']} (was {m0})")
        if am and am["naming"]:
            sv.call("type", text=f"{B['tag']}{have + bought + 1}"); time.sleep(0.3)
            sv.call("click", x=am["done"]["x"], y=am["done"]["y"]); time.sleep(1.5)
        if sv.state()["player"]["money"] <= m0 - CHICKEN:
            bought += 1
        for _ in range(20):
            if not sv.state().get("menu"): break
            am = sv.call("animal_menu")
            if am and am.get("ok"): sv.call("click", **am["ok"]); time.sleep(1.5)
            else: town.close_menu(); act.dismiss(); time.sleep(0.5)
    p = _prog(); p[B["count"]] = have + bought; _save(p)
    act.log(f"{kind} animals: bought {bought}, now {have + bought}")
    # feed: no silo, no winter grass -> 1 Hay per animal per day (wiki Hay 50g)
    n_all = p.get("chickens", 0) + p.get("cows", 0)
    want_hay = 7 * n_all - _have("Hay") - (p.get("chest") or {}).get("Hay", 0)
    tool_need = {"Barn": "Milk Pail", "Sheep": "Shears"}.get(kind)
    if tool_need and bought and not any(i["name"] == tool_need for i in act.inv()):
        act.walk(c["x"], c["y"], adjacent=True); act.use(c["x"], c["y"], right=True); time.sleep(0.8)
        if _pick_response("ShopMenu", lambda: (sv.state().get("menu") or {}).get("type") == "ShopMenu", [0]):
            time.sleep(0.6); town._last_shop = None
            town.buy({tool_need: 1}); town.close_menu()
            act.log(f"barn: {tool_need} {'bought' if any(i['name'] == tool_need for i in act.inv()) else 'NOT bought'}")
    if n_all and want_hay > 7 * n_all - 2 * n_all and sv.state()["player"]["money"] > want_hay * 50 + 1000:
        act.walk(c["x"], c["y"], adjacent=True); act.use(c["x"], c["y"], right=True); time.sleep(0.8)
        if _pick_response("ShopMenu", lambda: (sv.state().get("menu") or {}).get("type") == "ShopMenu", [0]):
            time.sleep(0.6); town._last_shop = None
            town.buy({"Hay": want_hay}); town.close_menu()
            act.log(f"chickens: hay now {_have('Hay')}")

def buy_feed():
    """W19: hay ran out (no silo) and the hens' friendship fell 60 -> 30. Keep >= 2 days of hay; buy a week."""
    p = _prog(); s = sv.state()
    n_all = p.get("chickens", 0) + p.get("cows", 0)
    if not n_all: return               # animal doors are never opened by the agent: hay all year
    hay = _have("Hay") + (p.get("chest") or {}).get("Hay", 0)
    if (p.get("chest") or {}).get("Hay", 0) >= 7 * n_all:
        return            # Sp 5 Y3: bought 35 Hay (1,750g) with 216 in the chest; money is for the rabbit
    if p.get("silo") and coop_ready("Silo"):
        if _abs_day(s) - p.get("silo_hay_day", -99) < 7: return        # hay bought now goes into the silo
        hay = 0
    elif hay >= 2 * n_all: return
    if not (700 <= s["time"] < 1330) or (s["day"] - 1) % 7 in (0, 1) or marnie_closed_holiday(s): return   # W21: arrived 16:50, shop shut at 16:00
    want = 7 * n_all - hay
    if s["player"]["money"] < want * 50 + 300: want = max(0, (s["player"]["money"] - 300) // 50)
    if want <= 0: return
    import projects
    if sv.state()["time"] < 900:
        act.goto("Forest"); _wait_open(900)
    act.goto("AnimalShop")
    c = projects.counter("AnimalShop", "Marnie")
    if not c: return
    act.walk(c["x"], c["y"], adjacent=True); act.use(c["x"], c["y"], right=True); time.sleep(0.8)
    if _pick_response("ShopMenu", lambda: (sv.state().get("menu") or {}).get("type") == "ShopMenu", [0]):
        time.sleep(0.6); town._last_shop = None
        town.buy({"Hay": want}); town.close_menu()
    if p.get("silo"):
        p = _prog(); p["silo_hay_day"] = _abs_day(s); _save(p)
    act.log(f"feed: hay {hay} -> {_have('Hay') + (p.get('chest') or {}).get('Hay', 0)} (silo {bool(p.get('silo'))})")

def run():
    p = _prog()
    act.log(f"animals: coop={p.get('coop')} chickens={p.get('chickens', 0)} barn={p.get('barn')} cows={p.get('cows', 0)}")
    for step in (build_coop, buy_chickens, build_silo, buy_feed, build_barn, buy_cows, upgrades, buy_upgrade_animals, care, care_barn):     # buy first, feed the same day
        try: step()
        except Exception as e:
            import traceback; act.log(f"animals.{step.__name__} failed: {e!r} @ {traceback.format_exc().splitlines()[-3].strip()}")
            try: town.close_menu()
            except Exception: pass

def coop_ready_silo_cached(p):
    return _abs_day(sv.state()) >= (p.get("silo") or {}).get("ordered", 999) + 3

def care_barn():
    return care("Barn")

def care(kind="Coop"):
    """Daily: enter the coop/barn, put hay on empty bench tiles (no silo), pet every animal, collect eggs,
    milk adult cows (wiki Milk Pail: milking by hand +5 friendship).
    Wiki (Animals): petting daily raises friendship (Large Eggs need friendship); unfed animals lose mood."""
    p = _prog(); B = SPEC[kind]
    if not p.get(B["count"]): return
    today = _abs_day(sv.state())
    if p.get(f"care_{kind}") == today: return            # W12: a restarted day fed and walked twice
    act.goto("Farm")
    if not coop_ready(kind): return
    s = sv.state()
    if s["time"] >= 2200: return
    import donate
    hay_needed = p.get(B["count"], 0)
    if kind == "Barn" and act.slot_of("Milk Pail") is None and (p.get("chest") or {}).get("Milk Pail"):
        donate.withdraw_bundle_items({"Milk Pail"})          # chest sync stored it until Sp 2 (not in TOOLS)
    if _have("Hay") < hay_needed and (p.get("chest") or {}).get("Hay"):
        if len(act.inv()) >= sv.state().get("backpack", 12) and not _have("Hay"):
            import play_day; play_day.chest_sync_and_ship()     # W26: full backpack -> hay never left the chest
        donate.withdraw_bundle_items({"Hay"})
    act.goto("Farm")
    a = sv.call("around", r=80)
    b = next((b for b in a.get("buildings", []) if kind in b["type"] and not b["building"]), None)
    if not b: act.log("coop care: no finished coop"); return
    # open the animal door on fair days outside winter: grazing replaces hay, and the pig finds Truffles only
    # outdoors (wiki Truffle). Animals walk back in by evening.
    s_now = sv.state()
    # Fa 28 Y2: opening the coop door first sent the hens out, then care found an empty coop (petted 0 for weeks,
    # friendship ~8 -> no Large Egg). Only the barn door, and only for a pig (Truffles need it outdoors).
    if kind == "Barn" and p.get("pigs") and s_now["season"] != "winter" and s_now["weather"] not in ("rain", "storm", "snow") and not b.get("adoor_open", True):
        ax, ay = b["adoor_x"], b["adoor_y"]
        if act.walk(ax, ay + 1, timeout=8) == "arrived":
            act.use(ax, ay, right=True)
            nb = next((x for x in sv.call("around", r=5).get("buildings", []) if x["x"] == b["x"] and x["y"] == b["y"]), {})
            act.log(f"{kind}: animal door {'opened' if nb.get('adoor_open') else 'did NOT open'} at {(ax, ay)}")
    door = (b["door_x"], b["door_y"])
    act.walk(door[0], door[1] + 1)
    act.use(door[0], door[1], right=True)
    try:
        sv.wait(lambda st: st["player"]["loc"] != "Farm", timeout=8)
    except TimeoutError:
        act.log(f"coop care: door {door} did not open"); return
    fed = pet = 0
    # W5 Y2: uncollected eggs block paths inside the coop: collect first, then feed and pet
    eggs_first = town.forage_nearby(r=20, max_items=80, products=True) if kind == "Coop" else 0
    # wiki Silo: "Hay can also be added to the silo by clicking the hay hoppers while holding the hay"
    # wiki Hay: the silo only STORES hay; it must be placed on the bench by hand. Right-click the hopper with empty
    # hands (not holding Hay) to take out one hay per animal. (Sp 8-10: holding Hay put the whole stack INTO the silo.)
    if _have("Hay") < hay_needed and p.get("silo") and coop_ready_silo_cached(p):
        hop = next((o for o in sv.call("around", r=20)["objects"] if "Hopper" in o["name"]), None)
        if hop and act.walk(hop["x"], hop["y"], adjacent=True, timeout=6) == "arrived":
            h0 = _have("Hay")
            act.use(hop["x"], hop["y"], right=True); act.dismiss()      # right-click with the Axe in hand
            act.log(f"care: hay from hopper {h0} -> {_have('Hay')}")
    # hay on empty bench tiles
    if _have("Hay"):
        bench = [t for t in sv.call("tile_prop", layer="Back", prop="Trough") if not t["has_obj"]]
        for t in bench[:max(0, hay_needed)]:
            if not _have("Hay"): break
            # W24: hungry hens crowd the tile in front of the bench, so "adjacent" walks failed at once and no hay
            # was placed for days. Try several standing tiles (diagonals reach too), and wait for hens to move.
            stood = False
            for _try in range(1):
                for st_t in ((t["x"], t["y"] + 1), (t["x"] - 1, t["y"] + 1), (t["x"] + 1, t["y"] + 1)):
                    r_ = act.walk(*st_t, timeout=6)
                    if r_ == "arrived": stood = True; break
                    # W1-W4 Y2: every bench walk failed, reason unknown -> log it with position + animals
                    act.log(f"care: walk to {st_t} -> {r_}; me {act.here()}; hens {[(x['x'], x['y']) for x in sv.call('around', r=30).get('animals', [])]}")
                if stood: break
                time.sleep(0.5)
            if not stood:
                act.log(f"care: bench {t['x'], t['y']} unreachable; stopping hand-feeding (silo pending)"); break
            sl = act.slot_of("Hay")
            if sl is not None and sl >= 12: sl = act.to_hotbar("Hay")
            if sl is None or sl >= 12: break
            n0 = _have("Hay")
            sv.call("use", x=t["x"], y=t["y"], slot=sl, right=True); act.wait_done("tool", 10)
            fed += _have("Hay") < n0
    # pet everyone
    for an in sv.call("around", r=30).get("animals", []):
        if an["pet"]: continue
        for _try in range(4):             # W19-20: animals wander; only 1-2 of 4 got petted. Re-locate, verify.
            cur = next((x for x in sv.call("around", r=30)["animals"] if x["name"] == an["name"]), an)
            if cur["pet"]: break
            r_ = act.walk(cur["x"], cur["y"], adjacent=True, timeout=8)
            if r_ != "arrived":
                act.log(f"care: pet walk to {an['name']} at {(cur['x'], cur['y'])} -> {r_}; me {act.here()}"); continue
            cur = next((x for x in sv.call("around", r=30)["animals"] if x["name"] == an["name"]), cur)
            act.use(cur["x"], cur["y"], right=True); act.dismiss()
            if (sv.state().get("menu") or {}).get("type") == "AnimalQueryMenu":   # W23: already petted -> info panel
                town.close_menu()
            act.log(f"care: pet {an['name']} at {(cur['x'], cur['y'])} from {act.here()[1]}")
        if next((x for x in sv.call("around", r=30)["animals"] if x["name"] == an["name"]), {}).get("pet"):
            pet += 1
    milked = 0
    if kind == "Barn" and act.slot_of("Milk Pail") is None and (p.get("chest") or {}).get("Milk Pail"):
        act.log("barn: Milk Pail is in the chest (Sp 2): fetch it tomorrow")   # inside the barn: no chest trip now
    if kind == "Barn" and act.slot_of("Milk Pail") is not None:
        for an in sv.call("around", r=30).get("animals", []):
            if not an["adult"]: continue
            if act.walk(an["x"], an["y"], adjacent=True) != "arrived": continue
            cur = next((x for x in sv.call("around", r=30)["animals"] if x["name"] == an["name"]), an)
            n0 = len(act.inv())
            act.use(cur["x"], cur["y"], tool="Milk Pail"); act.dismiss()
            milked += 1
        act.log(f"barn: milk pail used on {milked}")
    if kind == "Barn" and act.slot_of("Shears") is not None:
        sh = 0
        for an in sv.call("around", r=30).get("animals", []):
            if not an["adult"] or "Sheep" not in an["type"]: continue
            if act.walk(an["x"], an["y"], adjacent=True) != "arrived": continue
            cur = next((x for x in sv.call("around", r=30)["animals"] if x["name"] == an["name"]), an)
            act.use(cur["x"], cur["y"], tool="Shears"); act.dismiss(); sh += 1
        act.log(f"barn: shears used on {sh}")
    eggs = eggs_first + town.forage_nearby(r=20, max_items=12, products=True)
    st = sv.call("around", r=30)
    # Sp 10-14 Y3: the Deluxe Coop's animal door is open, so on fair mornings the hens were already outside and the
    # coop looked empty (petted 0 for days). Grazing outside sets mood to 255 (wiki Animals), so keep the door and pet
    # the animals out on the farm too.
    try: pet += pet_outdoors()
    except Exception as e: act.log(f"outdoor petting failed: {e!r}")
    p = _prog(); p[f"care_{kind}"] = today; p[f"types_{kind}"] = sorted({x["type"] for x in st.get("animals", [])}); _save(p)
    act.log(f"{kind} care: hay {fed}, petted {pet}, collected {eggs}; animals {[(x['name'], x['type'], x['friendship'], x['adult']) for x in st.get('animals', [])]}")
    act.goto("Farm")


def upgrade_reserve():
    """Money the barn chain still needs (Fa 1 Y2: 10,800g of Pumpkin Seeds left the Deluxe Barn unaffordable)."""
    import needs
    q = set(needs.quota()); p = _prog(); r = 0
    if "Truffle" in q:
        if not p.get("big_barn"): r += SPEC["Big Barn"]["cost"] + 20 * 200
        if not p.get("deluxe_barn"): r += SPEC["Deluxe Barn"]["cost"] + 20 * 300
        if not p.get("pigs"): r += SPEC["Deluxe Barn"]["price"]
    if ("Duck Feather" in q or "Duck Egg" in q or "Rabbit's Foot" in q) and not p.get("big_coop"):
        r += SPEC["Big Coop"]["cost"] + SPEC["Big Coop"]["price"]
    if "Rabbit's Foot" in q:
        if not p.get("deluxe_coop"): r += SPEC["Deluxe Coop"]["cost"]
        if not p.get("rabbits"): r += SPEC["Deluxe Coop"]["price"]
    return r


def collect_truffles():
    """Spring-fall: the pig digs Truffles on the farm while outdoors (wiki Truffle). They sit on the ground as
    spawned objects until picked up. Pick every Truffle on the farm in the evening (Chef's bundle needs one)."""
    s = sv.state()
    if s["season"] == "winter" or not _prog().get("pigs"): return 0
    act.goto("Farm")
    got = 0
    for _ in range(12):
        tr = [o for o in sv.call("around", r=80)["objects"] if o["name"] == "Truffle"]
        if not tr: break
        _, me = act.here()
        o = min(tr, key=lambda o: abs(o["x"] - me[0]) + abs(o["y"] - me[1]))
        if act.walk(o["x"], o["y"], adjacent=True, timeout=60) != "arrived":
            act.log(f"truffle at {(o['x'], o['y'])} unreachable"); break
        n0 = _have("Truffle")
        act.use(o["x"], o["y"], right=True); act.dismiss()
        if _have("Truffle") > n0: got += 1
        else: act.log(f"truffle at {(o['x'], o['y'])}: pick failed"); break
    if got: act.log(f"collected {got} Truffle(s)")
    return got


def pet_outdoors(max_n=12):
    """Pet every unpetted farm animal standing outside on the Farm (wiki: petting daily = friendship + mood)."""
    act.goto("Farm")
    done = 0; tried = set()
    for _ in range(max_n):
        out = [a for a in sv.call("around", r=80).get("animals", []) if not a["pet"] and a["name"] not in tried]
        if not out: break
        _, me = act.here()
        a = min(out, key=lambda a: abs(a["x"] - me[0]) + abs(a["y"] - me[1]))
        tried.add(a["name"])
        for _try in range(3):
            cur = next((x for x in sv.call("around", r=80)["animals"] if x["name"] == a["name"]), None)
            if not cur or cur["pet"]: break
            if act.walk(cur["x"], cur["y"], adjacent=True, timeout=20) != "arrived": continue
            cur = next((x for x in sv.call("around", r=80)["animals"] if x["name"] == a["name"]), cur)
            act.use(cur["x"], cur["y"], right=True); act.dismiss()
            if (sv.state().get("menu") or {}).get("type") == "AnimalQueryMenu": town.close_menu()
        if next((x for x in sv.call("around", r=80)["animals"] if x["name"] == a["name"]), {}).get("pet"):
            done += 1
    if done: act.log(f"petted {done} animals outdoors")
    return done
