"""Crafting through the game menu, placing and using chests."""
import time
import sv, act, town

def open_tab(name):
    s = sv.state()
    if not s.get("menu"):
        sv.call("tap", key="Escape", ticks=5); time.sleep(0.5)
    w = sv.widgets()
    tab = next(x for x in w["widgets"] if x["field"] == "tabs" and x["name"] == name)
    sv.call("click", x=tab["x"], y=tab["y"]); time.sleep(0.5)

@act.slow
def craft(recipe, n=1):
    # the crafted item lands on the cursor; with no free backpack slot it is lost/dropped (Su 2 scarecrow)
    if len(sv.state()["inventory"]) >= sv.state().get("backpack", 12):
        act.log(f"cannot craft {recipe}: backpack full"); return 0
    open_tab("crafting")
    made = 0
    for _ in range(n):
        r = next((x for x in (sv.call("recipes") or []) if x["name"] == recipe), None)
        if not r:
            # recipes are paged (Fa 25: Tapper sat on page 2); flip down, then up, like a player scrolling
            for btn in ("downButton", "downButton", "upButton", "upButton", "upButton"):
                w = next((x for x in sv.widgets()["widgets"] if x["field"] == btn), None)
                if not w: continue
                sv.call("click", x=w["x"], y=w["y"]); time.sleep(0.3)
                r = next((x for x in (sv.call("recipes") or []) if x["name"] == recipe), None)
                if r: break
        if not r or not r["can"]:
            act.log(f"cannot craft {recipe} ({'not on any page: recipe unknown?' if not r else 'missing ingredients'})"); break
        sv.call("click", x=r["x"], y=r["y"]); time.sleep(0.3)
        made += 1
    # crafted item sits on the cursor: drop it into the first empty backpack slot
    if made:
        filled = {i["slot"] for i in sv.state()["inventory"]}
        w = sv.widgets()
        bp = sv.state().get("backpack", 12)
        empty = [x for x in w["widgets"] if x["field"].endswith("inventory.slot") and x["i"] not in filled and x["i"] < bp]
        if empty:
            sv.call("click", x=empty[0]["x"], y=empty[0]["y"]); time.sleep(0.3)
    town.close_menu()
    act.log(f"crafted {made}x {recipe}")
    return made

def place(item, x, y):
    act.walk(x, y, adjacent=True)
    act.use(x, y, tool=item)

def deposit(chest_xy, keep):
    """Open chest, click every backpack item not in keep (moves it into the chest)."""
    act.walk(*chest_xy, adjacent=True)
    act.use(*chest_xy, right=True)
    sv.wait(lambda s: (s.get("menu") or {}).get("type") == "ItemGrabMenu", timeout=5)
    for it in list(sv.state()["inventory"]):
        if it["name"] in keep:
            continue
        w = sv.widgets()
        slot = next((x for x in w["widgets"] if x["field"] == "inventory.slot" and x["i"] == it["slot"]), None)
        if slot:
            sv.call("click", x=slot["x"], y=slot["y"]); time.sleep(0.2)
            act.log(f"stored {it['name']} x{it['stack']}")
    town.close_menu()


JUNK = ["Green Algae", "White Algae", "Seaweed", "River Jelly", "Sea Jelly", "Moss", "Bug Meat", "Cookie", "Pink Cake",
        "Acorn", "Maple Seed", "Pine Cone", "Dandelion", "Wild Horseradish", "Corn",
        "Bone Fragment", "Femur", "House Plant", "Strange Bun", "Rubber Boots", "Lead Rod", "Cherry Bomb", "Egg", "Milk", "Fiber",
        "Crystal Floor", "Wood Floor", "Straw Floor", "Stone Floor", "Weathered Floor", "Wood Path", "Gravel Path", "Cobblestone Path"]  # Su 17 Y2: chest full (36 slots), ores stayed in the backpack

def ensure_chest(xy):
    """Fresh save: the main chest does not exist yet. Clear the tile, craft a Chest (50 Wood, known from the start)
    and place it at xy. Returns True when a chest stands at xy."""
    act.walk(*xy, adjacent=True)
    if any(o["name"] == "Chest" and (o["x"], o["y"]) == tuple(xy) for o in sv.call("around", r=3)["objects"]):
        return True
    if not any(i["name"] == "Chest" for i in act.inv()):
        wood = sum(i["stack"] for i in act.inv() if i["name"] == "Wood")
        if wood < 50:
            act.log(f"CHEST: no main chest yet and only {wood} Wood (need 50)"); return False
        if not craft("Chest"): return False
    import farming
    try: farming.clear(tuple(xy))
    except Exception as e: act.log(f"CHEST: clearing {xy} failed: {e!r}")
    place("Chest", *xy)
    ok = any(o["name"] == "Chest" and (o["x"], o["y"]) == tuple(xy) for o in sv.call("around", r=3)["objects"])
    act.log(f"CHEST: placed main chest at {xy}: {ok}")
    return ok

@act.slow
def sync_chest(chest_xy, quota, materials, keep_inv):
    """One chest visit = source of truth. For each item:
       - materials: all go into the chest
       - quota items: chest holds exactly min(total, quota); extra comes out to be shipped
       - keep_inv (tools, seeds): stay in the backpack
    Returns names now in the backpack that should be shipped."""
    if not ensure_chest(chest_xy):        # no chest yet: ship sellables directly, keep materials and bundle items
        return {i["name"] for i in act.inv() if i["name"] not in keep_inv and i["name"] not in materials and i["name"] not in quota}
    act.walk(*chest_xy, adjacent=True)
    act.use(*chest_xy, right=True)
    sv.wait(lambda s: (s.get("menu") or {}).get("type") == "ItemGrabMenu", timeout=5)
    def slot_widget(field, i):
        return next(x for x in sv.widgets()["widgets"] if x["field"] == field and x["i"] == i)
    # 1) pull over-quota stacks out of the chest
    names = {g["name"] for g in sv.state()["menu"].get("grab", [])}
    for name in names:
        # re-read each time: the chest compacts after a take, so slot indexes go stale
        it = next((g for g in sv.state()["menu"].get("grab", []) if g["name"] == name), None)
        q = quota.get(name)
        if it and q is not None and it["stack"] > q and name not in materials:
            w = slot_widget("ItemsToGrabMenu.slot", it["i"])
            sv.call("click", x=w["x"], y=w["y"]); time.sleep(0.25)
            mine = next((i for i in sv.state()["inventory"] if i["name"] == it["name"]), None)
            if mine and q:
                d = slot_widget("inventory.slot", mine["slot"])
                for _ in range(q):
                    sv.call("click", x=d["x"], y=d["y"], right=True); time.sleep(0.12)
    # 1b) chest nearly full (W17: 35 of 36 slots) -> bundle minerals could not go in and were shipped.
    #     Take junk stacks out; chest_sync_and_ship ships them.
    names = [g["name"] for g in sv.state()["menu"].get("grab", [])]
    if len(names) >= 30:
        for name in [n for n in JUNK if n in names and n not in quota]:
            if len(sv.state()["inventory"]) >= sv.state().get("backpack", 12) - 1: break
            it = next((g for g in sv.state()["menu"].get("grab", []) if g["name"] == name), None)
            if not it: continue
            w = slot_widget("ItemsToGrabMenu.slot", it["i"])
            sv.call("click", x=w["x"], y=w["y"]); time.sleep(0.25)
    # 1c) decorations are waste (Amer, Su 18 Y2): furniture (F) / decor (-24) in the backpack goes in the trash
    trash = next((x for x in sv.widgets()["widgets"] if x["field"] == "trashCan"), None)
    try:
        import guild; best = (guild.owned() or [None])[0]
    except Exception: best = None
    def _waste(i):     # furniture, decor, boots, weapons weaker than the best one (they cannot be shipped)
        return (str(i.get("id", "")).startswith("(F)") or i.get("cat") in (-24, -97)
                or (i.get("cat") == -98 and best and i["name"] != best))
    for it in [i for i in sv.state()["inventory"] if _waste(i)]:
        if it["name"] in quota or not trash: continue
        d = slot_widget("inventory.slot", it["slot"]); sv.call("click", x=d["x"], y=d["y"]); time.sleep(0.2)
        sv.call("click", x=trash["x"], y=trash["y"]); time.sleep(0.25)
        act.log(f"trashed decoration {it['name']} x{it['stack']}")
    # 2) push backpack items in
    chest = {g["name"]: g["stack"] for g in sv.state()["menu"].get("grab", [])}
    for it in list(sv.state()["inventory"]):
        n = it["name"]
        if n in keep_inv:
            continue
        if n in materials or n not in quota:
            if n in materials:
                d = slot_widget("inventory.slot", it["slot"]); sv.call("click", x=d["x"], y=d["y"]); time.sleep(0.2)
            continue
        need = quota[n] - chest.get(n, 0)
        if need > 0:
            d = slot_widget("inventory.slot", it["slot"])
            if it["stack"] <= need:
                sv.call("click", x=d["x"], y=d["y"])
            else:
                for _ in range(need):
                    sv.call("click", x=d["x"], y=d["y"], right=True); time.sleep(0.12)
            chest[n] = chest.get(n, 0) + min(need, it["stack"])
            time.sleep(0.2)
    try:
        import play_day, needs
        pr = play_day.prog()
        real = {}
        for g in sv.state()["menu"].get("grab", []):
            real[g["name"]] = real.get(g["name"], 0) + g["stack"]
        pr["chest_main_names"] = len(real)
        for cont in (pr.get("chest_extra") or {}).values():     # extra chests count too (materials)
            for k, v in cont.items(): real[k] = real.get(k, 0) + v
        pr["chest"] = real                      # snapshot of the real chest, read by the donate planner
        pr.pop("chest_has_bundle_items", None)
        play_day.save_prog(pr)
    except Exception:
        pass
    town.close_menu()
    return {i["name"] for i in sv.state()["inventory"] if i["name"] not in keep_inv and i["name"] not in materials}


# ---------------- extra chests (Amer, Su 18 Y2: "u can use more chests for storage") ----------------
# Main chest CHEST (74,14) keeps bundle items. Extra chests hold materials (ores, bars, wood, stone...).
# Wiki Chest: 50 Wood, 36 item types per chest.
MAIN = (74, 14)
SPOTS = [(75, 14), (76, 14), (77, 14), (73, 14), (75, 13), (76, 13), (77, 13), (78, 14)]


def extra_chests():
    import play_day
    return [tuple(c) for c in play_day.prog().get("extra_chests", [])]


def _record(xy, contents):
    import play_day
    p = play_day.prog()
    p.setdefault("chest_extra", {})[f"{xy[0]},{xy[1]}"] = contents
    play_day.save_prog(p)


def _relocate(xy):
    """1.6: hitting a full chest with a tool shoves it one tile (Su 1x Y3: (75,14) -> (76,14), a week of timeouts).
    If no chest stands at xy, adopt an unknown chest within 2 tiles and update progress.json."""
    import play_day
    objs = [o for o in sv.call("around", r=40)["objects"] if o["name"] == "Chest"]
    if any((o["x"], o["y"]) == tuple(xy) for o in objs): return tuple(xy)
    p = play_day.prog()
    known = {tuple(c) for c in (p.get("extra_chests") or [])} | {tuple(play_day.CHEST)}
    cand = [o for o in objs if (o["x"], o["y"]) not in known and abs(o["x"] - xy[0]) + abs(o["y"] - xy[1]) <= 2]
    if not cand: return tuple(xy)
    new = (cand[0]["x"], cand[0]["y"])
    p["extra_chests"] = [list(new) if tuple(c) == tuple(xy) else c for c in p.get("extra_chests", [])]
    ce = p.get("chest_extra") or {}
    k = f"{xy[0]},{xy[1]}"
    if k in ce: ce[f"{new[0]},{new[1]}"] = ce.pop(k)
    play_day.save_prog(p)
    act.log(f"chest moved {tuple(xy)} -> {new}: progress updated")
    return new

def _open(xy):
    if act.here()[0] == "Farm":
        try: xy = _relocate(xy)
        except Exception as e: act.log(f"chest relocate check failed: {e!r}")
    # Su 12-19 Y3: chest (75,14) never opened from (75,15) below it; every Hay/chest step timed out for a week.
    # Try the default adjacent tile, then each side explicitly.
    tries = [None, (xy[0], xy[1] - 1), (xy[0] - 1, xy[1]), (xy[0] + 1, xy[1]), (xy[0], xy[1] + 1)]
    for st in tries:
        if st is None: act.walk(*xy, adjacent=True)
        elif act.walk(*st, timeout=20) != "arrived": continue
        act.use(*xy, right=True)
        try:
            sv.wait(lambda s: (s.get("menu") or {}).get("type") == "ItemGrabMenu", timeout=5); return
        except TimeoutError:
            act.log(f"chest {xy}: did not open from {act.here()[1]}")
    raise TimeoutError(f"chest {xy} would not open from any side")


def _grab_contents():
    out = {}
    for g in sv.state()["menu"].get("grab", []):
        out[g["name"]] = out.get(g["name"], 0) + g["stack"]
    return out


def new_chest():
    """Craft a Chest (50 Wood) and place it next to the main chest."""
    import donate
    have = sum(i["stack"] for i in act.inv() if i["name"] == "Wood")
    if have < 50:
        donate.withdraw_bundle_items({"Wood"})
    if craft("Chest") < 1:
        act.log("CHEST: could not craft a Chest"); return None
    a = sv.call("around", r=10)
    taken = {(o["x"], o["y"]) for o in a["objects"]} | set(extra_chests()) | {MAIN}
    rows = sv.call("grid")["rows"]
    for x, y in SPOTS:
        if (x, y) in taken or rows[y][x] != ".": continue
        place("Chest", x, y)
        if act.slot_of("Chest") is None:
            import play_day
            p = play_day.prog(); p.setdefault("extra_chests", []).append([x, y]); play_day.save_prog(p)
            act.log(f"CHEST: placed extra chest at {(x, y)}")
            return (x, y)
    act.log("CHEST: no free spot for an extra chest")
    return None


def store_materials(materials):
    """Put carried materials into the extra chests; make a new chest when they are all full."""
    for _ in range(3):
        left = [i for i in act.inv() if i["name"] in materials]
        if not left: return
        for xy in extra_chests():
            _open(xy)
            for it in list(sv.state()["inventory"]):
                if it["name"] not in materials: continue
                w = next((x for x in sv.widgets()["widgets"] if x["field"] == "inventory.slot" and x["i"] == it["slot"]), None)
                if w: sv.call("click", x=w["x"], y=w["y"]); time.sleep(0.2)
            _record(xy, _grab_contents())
            town.close_menu()
            if not any(i["name"] in materials for i in act.inv()): return
        if not new_chest(): return


def move_materials_out_of_main(materials):
    """Main chest crowded (>= 28 item types): move material stacks to the extra chests."""
    if not extra_chests(): return
    _open(MAIN)
    names = [g["name"] for g in sv.state()["menu"].get("grab", [])]
    if len(names) < 28:
        town.close_menu(); return
    moved = []
    for name in [n for n in dict.fromkeys(names) if n in materials]:
        st = sv.state()
        if len(st["inventory"]) >= st.get("backpack", 12) - 1: break
        it = next((g for g in st["menu"].get("grab", []) if g["name"] == name), None)
        if not it: continue
        w = next(x for x in sv.widgets()["widgets"] if x["field"] == "ItemsToGrabMenu.slot" and x["i"] == it["i"])
        sv.call("click", x=w["x"], y=w["y"]); time.sleep(0.25); moved.append(name)
    town.close_menu()
    if moved:
        act.log(f"CHEST: moving {moved} from the main chest to extra chests")
        store_materials(materials)
