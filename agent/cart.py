"""Traveling Cart (wiki): Cindersap Forest, Friday + Sunday 6:00-20:00, 10 random items, stock 1 or 5.
Year 1 is the only Red Cabbage Seeds route (Dye bundle) and sells bundle items out of season.
Buys: Red Cabbage Seeds (summer, while 9 days still fit) and any still-needed bundle item, if affordable."""
import time
import sv, act, town, needs

# decompiled Forest.checkAction: shop tile = cart top-left + (4, 1); top-left = map property
# TravelingCartPosition, default (23, 10). Neighbours probed in case the map property moves it.
PROBE = [(27, 11)] + [(23 + dx + 4, 10 + dy + 1) for dy in (-1, 0, 1, 2) for dx in (-3, -2, -1, 1, 2, 3)]

def _prog():
    import play_day; return play_day.prog()

def _save(p):
    import play_day; play_day.save_prog(p)

def is_cart_day(s):
    return s["day"] % 7 in (5, 0)        # day 1 = Monday

def open_cart():
    act.goto("Forest")
    p = _prog()
    tiles = []
    try:
        c = sv.call("cart")                  # mod: Forest.GetTravelingMerchantCartTile() + (4, 1)
        if c and c.get("shop_x") is not None: tiles.append((c["shop_x"], c["shop_y"]))
    except Exception:
        pass
    tiles += ([tuple(p["cart_tile"])] if p.get("cart_tile") else []) + PROBE[:4]     # probing cost 4 h on Su 14
    for t in tiles:
        if act.walk(t[0], t[1] + 1, adjacent=False) != "arrived" and act.walk(*t, adjacent=True) != "arrived":
            # cart collision rects block the walker's full-tile check under the cart (Su 14): stand two
            # tiles below and step up with the movement key, like a player squeezing in
            if act.walk(t[0], t[1] + 2) != "arrived":
                continue
            up = sv.state()["keys"]["up"]
            sv.call("hold", down=[up]); time.sleep(0.25); sv.call("hold", up=[up]); time.sleep(0.2)
        act.use(*t, right=True)
        time.sleep(0.8)
        m = (sv.state().get("menu") or {}).get("type")
        if m == "ShopMenu":
            if p.get("cart_tile") != list(t):
                p = _prog(); p["cart_tile"] = list(t); _save(p)
                act.log(f"cart: opened at tile {t}")
            time.sleep(0.6)
            return True
        if m:
            act.dismiss(); town.close_menu()
    act.log("cart: could not open the cart")
    return False

def visit():
    s = sv.state()
    if not is_cart_day(s) or s["time"] >= 1900:
        return
    p = _prog()
    if p.get("cart_day") == [s["year"], s["season"], s["day"]]:
        return
    p["cart_day"] = [s["year"], s["season"], s["day"]]; _save(p)
    if not open_cart():
        return
    town._last_shop = None
    sh = sv.call("shop") or {"items": []}
    act.log(f"cart stock: {[(i['name'], i['price'], i['stock']) for i in sh['items']]}")
    q = needs.quota()
    money = sv.state()["player"]["money"]
    want = {}
    import play_day
    grown = set(play_day.CROP_SEED) - {"Red Cabbage"}        # crops we grow ourselves: don't pay cart prices
    items = sorted(sh["items"], key=lambda it: -it["price"])  # rare/expensive bundle items first
    for it in items:
        n = it["name"]
        if n == "Red Cabbage Seeds" and "Red Cabbage" in q and s["season"] == "summer" and s["day"] + 9 <= 28:
            k = 2
        elif n in q and it["price"] > 0 and n not in grown:
            k = 1
        else:
            continue
        k = min(k, it["stock"] if it["stock"] > 0 else k)
        if it["price"] * k <= money - 100:
            want[n] = k; money -= it["price"] * k
    if want:
        act.log(f"cart: buying {want}")
        town.buy(want)
    town.close_menu()
    if act.slot_of("Red Cabbage Seeds") is not None:
        import farming
        act.goto("Farm", 64, 24)
        act.log(f"cart: planted Red Cabbage: {farming.replant('Red Cabbage Seeds')}")
