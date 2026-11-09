"""Play one full in-game day autonomously, then sleep (day-end save). Logs to logs/ and RUNLOG.csv."""
import sys, time, json, os
import sv, act, farming, town, daily, craft, needs

CHEST = (74, 14)
TOOLS = {f"{t} {b}" for t in ("Copper", "Steel", "Gold", "Iridium") for b in ("Axe", "Hoe", "Watering Can", "Pickaxe")} | {"Axe", "Hoe", "Watering Can", "Pickaxe", "Scythe", "Bamboo Pole", "Training Rod", "Fiberglass Rod", "Iridium Rod", "Rusty Sword", "Wooden Blade", "Femur", "Steel Smallsword", "Silver Saber", "Galaxy Sword", "Milk Pail", "Shears"}
STATE_FILE = os.path.join(os.path.dirname(__file__), "progress.json")

def prog():
    try: return json.load(open(STATE_FILE))
    except Exception: return {}

def save_prog(p): json.dump(p, open(STATE_FILE, "w"), indent=1)

def seeds_in_inv():
    return [i["name"] for i in act.inv() if i["name"].endswith("Seeds") or i["name"].endswith("Sapling") or i["name"] in ("Bean Starter",)]

# Amer W24 Y2: "sell all unused items". Kept: building materials, animal feed, machines, tools/weapons/clothes,
# bundle items (quota). Everything else in the chests is shipped.
SURPLUS_KEEP = {"Wood", "Stone", "Hay", "Fiber", "Hardwood", "Coal", "Warp Totem: Farm", "Keg", "Tapper", "Preserves Jar",
                "Mystery Box", "Rice Shoot", "House Plant", "Monster Compendium", "Sonar Bobber", "Lead Rod"}
NO_SHIP_CATS = {-99, -98, -97, -96, -95, -100, -24, -9, -22}   # tools, weapons, boots, rings, hats, clothing, furniture, big craftables, tackle

def sell_surplus():
    p = prog()
    allc = dict(p.get("chest") or {})
    for c in (p.get("chest_extra") or {}).values():
        for k, v in c.items(): allc[k] = allc.get(k, 0) + v
    q = set(needs.quota())
    names = sorted(n for n in allc if n not in SURPLUS_KEEP and n not in q and n not in TOOLS
                   and not any(w in n for w in ("Sword", "Saber", "Hat", "Helmet", "Shirt", "Boots", "Ring", "Scroll", "Rod", "Pole", "Dagger", "Club")))
    if not names: return
    act.log(f"sell surplus: {names}")
    import donate
    for _round in range(6):
        free = sv.state().get("backpack", 12) - len(act.inv())
        batch = [n for n in names if not any(i["name"] == n for i in act.inv())][:max(0, free - 1)]
        if not batch: break
        donate.withdraw_bundle_items(set(batch))
        got = {i["name"] for i in act.inv() if i["name"] in batch and i.get("cat") not in NO_SHIP_CATS}
        if not got: break
        m0 = sv.state()["player"]["money"]
        daily.ship(got)
        names = [n for n in names if n not in got]
        act.log(f"sell surplus: shipped {sorted(got)}")

def chest_sync_and_ship():
    """Single source of truth = the chest's real contents (no counters)."""
    act.goto("Farm")
    if os.path.exists(os.path.join(os.path.dirname(__file__), "ANIMALS")):
        try: sell_surplus()
        except Exception as e: act.log(f"sell surplus failed: {e!r}")
    if os.path.exists(os.path.join(os.path.dirname(__file__), "ANIMALS")):
        # W22 Y2: animal goods piled up in the chest (not sellable then). Take the stored stock out once to ship it.
        stock = {n for n in ("Egg", "Brown Egg", "Milk", "Large Milk") if (prog().get("chest") or {}).get(n) and n not in needs.quota()}
        if stock and len(act.inv()) + len(stock) <= sv.state().get("backpack", 12):
            import donate; donate.withdraw_bundle_items(stock)
    inv = act.inv()
    keep = TOOLS | set(seeds_in_inv())
    if "Maki Roll" in needs.quota():          # Maki Roll = any fish + Seaweed + Rice (wiki): never ship them
        fish = sorted((i for i in inv if i.get("cat") == -4), key=lambda i: i.get("price", 0))
        keep = keep | {"Seaweed", "Rice", "Cookout Kit"} | ({fish[0]["name"]} if fish else set())
    materials = {i["name"] for i in inv if not daily.sellable(i) and i["name"] not in keep}
    import guild
    best = guild.owned()
    weaker = {w[0] for w in guild.WEAPONS if best and w[0] != best[0]}
    keep -= weaker
    materials |= weaker                                                          # park weaker weapons in the chest
    materials |= {"Wood", "Stone", "Sap", "Coal", "Copper Ore", "Iron Ore", "Gold Ore", "Fiber", "Clay", "Bait", "Slime", "Hardwood", "Copper Bar", "Iron Bar", "Gold Bar", "Refined Quartz", "Basic Fertilizer", "Scarecrow", "Furnace"}
    quota = needs.quota()
    if "Jelly" in quota or "Wine" in quota:   # keep one fruit stack for the Preserves Jar (Jelly) or the Keg (Wine)
        # Su 23 Y2: this kept ALL 276 Blueberries (~14k g) for a keg that takes one fruit. Keep the cheapest small fruit.
        tot = {}
        for i in inv:
            if i.get("cat") == -79 and i["name"] not in quota:
                tot[i["name"]] = tot.get(i["name"], 0) + i["stack"] * max(1, i.get("price", 0))
        cheap = [n for n, v in sorted(tot.items(), key=lambda kv: kv[1]) if v <= 1000]
        if cheap: keep = keep | {cheap[0]}
    mats = {n for n in materials - set(quota) if n not in craft.JUNK}   # bundle items -> main chest; junk -> ship/trash
    mats = {n for n in mats if not any(i["name"] == n and (str(i.get("id", "")).startswith("(F)") or i.get("cat") in (-24, -97, -98)) for i in inv)}
    if craft.extra_chests() or len(prog().get("chest") or {}) >= 30:
        craft.store_materials(mats)       # Amer: more chests for storage (materials -> extra chests)
    ship_names = craft.sync_chest(CHEST, quota, materials, keep)
    try: craft.move_materials_out_of_main(mats)
    except Exception as e: act.log(f"CHEST: moving materials failed: {e!r}")
    ship_names = {n for n in ship_names if any(i["name"] == n and daily.sellable(i) for i in act.inv())}
    ship_names |= {i["name"] for i in act.inv() if i["name"] in craft.JUNK and i["name"] not in quota and i["name"] not in keep}
    ship_names -= set(needs.quality_holds())     # gold Corn/Melon for Quality Crops: never junk
    if "Maki Roll" in quota: ship_names -= {"Seaweed", "Rice"}   # Maki Roll ingredients (Seaweed is in craft.JUNK)
    # never ship a bundle item: if the chest could not take it, carry it (W17: Frozen Tear + Aquamarine shipped)
    chest_now = prog().get("chest") or {}
    kept = {n for n in ship_names if n in quota and chest_now.get(n, 0) < quota[n]}
    # Su 19 Y2: 15 Wheat in 3 quality stacks, quota 10 -> 5 shipped, yet no stack of 10 existed. A bundle slot takes
    # one stack: never ship any bundle item (the surplus is small; donation frees it later).
    kept |= {n for n in ship_names if n in quota}
    if kept: act.log(f"chest short for bundle items {sorted(kept)}: carrying them")
    ship_names -= kept
    # keep one food stack for the mines (cheapest gold per HP healed, never a bundle item)
    # small stacks only: Su 15-22 the rule kept ~300 Blueberries (~16k g, the money crop) unsold as "food"
    food = [i for i in act.inv() if i.get("edible", -300) > 0 and i.get("heal", 0) > 0 and i["name"] not in quota
            and i.get("price", 0) * i["stack"] <= 300]
    for f in sorted(food, key=lambda i: i.get("price", 0) / max(1, i["heal"]))[:3]:
        ship_names.discard(f["name"])
        act.log(f"keeping food: {f['name']} x{f['stack']} (+{f['heal']} HP each)")
    ship_names -= keep
    if ship_names:
        daily.ship(ship_names)

CROP_SEED = {"Parsnip": "Parsnip Seeds", "Green Bean": "Bean Starter", "Cauliflower": "Cauliflower Seeds", "Potato": "Potato Seeds",
             "Tomato": "Tomato Seeds", "Hot Pepper": "Pepper Seeds", "Blueberry": "Blueberry Seeds", "Melon": "Melon Seeds",
             "Corn": "Corn Seeds", "Eggplant": "Eggplant Seeds", "Pumpkin": "Pumpkin Seeds", "Yam": "Yam Seeds",
             "Wheat": "Wheat Seeds", "Red Cabbage": "Red Cabbage Seeds", "Sunflower": "Sunflower Seeds", "Poppy": "Poppy Seeds"}   # wiki "seed" field

def buy_bundle_seeds():
    """Season rule (Amer): every bundle crop of this season gets planted while it can still mature.
    2 seeds per crop (one spare), once per season; growth days from the wiki."""
    s = sv.state()
    if s["time"] >= 1630 or (s["day"] - 1) % 7 == 2:          # Pierre 9-17, closed Wednesday
        return
    import seasons
    p = prog(); key = f"{s['year']}-{s['season']}"
    done = set(p.setdefault("bundle_seeds", {}).setdefault(key, []))
    q = needs.quota()
    # Su 9 Y2: 15 Wheat in 3 quality stacks (5/3/7); a bundle slot takes one stack of 10. Re-buy (double) when the
    # first planting has had time to grow and no single stack fills the slot.
    import seasons as _se
    bought = p.setdefault("bundle_seeds_day", {})
    best = {}
    for it in act.inv(): best[it["name"]] = max(best.get(it["name"], 0), it["stack"])
    redo = set()
    for crop in list(done):
        gi = _se.item_info([crop]).get(crop) or {}
        d0 = bought.get(f"{key}-{crop}")
        if crop in q and best.get(crop, 0) < q[crop] and d0 and s["day"] >= d0 + (gi.get("growth") or 28) + 1:
            done.discard(crop); redo.add(crop)
            act.log(f"bundle seeds: re-buying {crop} (best single stack {best.get(crop, 0)} < {q[crop]})")
    info = seasons.item_info([c for c in CROP_SEED if c in q])
    want = {}
    for crop, seed in CROP_SEED.items():
        i = info.get(crop)
        if crop not in q or crop in done or not i or s["season"] not in i["seasons"]:
            continue
        if crop == "Red Cabbage" and s["year"] == 1:
            continue                       # wiki: Pierre sells Red Cabbage Seeds from Year 2 (Traveling Cart only in Y1)
        if i["growth"] and s["day"] + i["growth"] > 28:
            act.log(f"SEASON: too late to plant {crop} ({i['growth']} days)"); continue
        n_need = q.get(crop, 1)                # Fodder wants 10 Wheat: Fa 1 bought only 2 seeds
        n_need = n_need * 2 if n_need > 1 else n_need     # quality spread: one same-quality stack must reach n
        want[seed] = n_need + max(1, n_need // 5) if s["player"]["money"] > 2500 else n_need
    if not want or s["player"]["money"] < 60:
        return
    if s.get("backpack", 12) - len(act.inv()) < 2:      # Su 13-16 Y2: full backpack = every Wheat Seeds buy failed
        chest_sync_and_ship()
    act.log(f"bundle seeds for {s['season']}: {want}")
    town.open_shop("SeedShop")
    town.buy(want)
    town.close_menu()
    act.goto("Farm")
    for seed in want:
        if act.slot_of(seed) is not None:
            act.log(f"planted {seed}: {farming.replant(seed)}")
            c = next(c for c, sd in CROP_SEED.items() if sd == seed)
            done.add(c); bought[f"{key}-{c}"] = s["day"]
    p = prog(); p.setdefault("bundle_seeds", {})[key] = sorted(done); p["bundle_seeds_day"] = bought; save_prog(p)

def buy_seeds():
    """Money plan (wiki prices): backpack 2,000g first; save for Strawberry Seeds at the Egg Festival (Sp 13);
    cauliflower (matures in 12 days) with what is left, only while it can mature by Sp 28."""
    s = sv.state()
    if s["season"] != "spring" or s["time"] >= 1630 or (s["day"] - 1) % 7 == 2:   # Pierre 9-17, closed Wed
        return
    if s["year"] > 1:
        # Y2 Sp 2: this Y1 money logic spent 11,680g on 146 Cauliflower; watering 160+ crops ran out of stamina.
        _, feats, _ = farming.tile_info(r=40)
        if sum(1 for f in feats.values() if f["type"] == "HoeDirt" and "crop" in f) >= 90: return
    money, bp = s["player"]["money"], s.get("backpack", 12)
    if bp == 12 and money >= 2000:
        town.open_shop("SeedShop")
        town.close_menu()
        bb = next(a for a in sv.call("actions") if a["action"] == "BuyBackpack")
        act.walk(bb["x"], bb["y"], adjacent=True); act.use(bb["x"], bb["y"], right=True)
        for _ in range(10):
            time.sleep(0.4)
            yes = [w for w in sv.widgets()["widgets"] if w["field"] == "responseCC"]
            if yes: sv.call("click", x=yes[0]["x"], y=yes[0]["y"]); break
        time.sleep(1); act.dismiss()
        act.log(f"backpack -> {sv.state().get('backpack')} slots, money {sv.state()['player']['money']}")
        money = sv.state()["player"]["money"]
    reserve = 1000 if s["day"] < 13 else 100          # strawberries on Sp 13
    if s["day"] > 16 or money - reserve < 160:
        return
    n = (money - reserve) // 80
    town.open_shop("SeedShop")
    town.buy({"Cauliflower Seeds": n})
    town.close_menu()
    act.goto("Farm"); act.log(f"planted cauliflower: {farming.replant('Cauliflower Seeds')}")

MAX_CROPS = 80          # hand watering: ~2 energy per tile, basic can (lesson C8)

def summer_money():
    """Wiki: Blueberry Seeds 80g (Pierre), 13 days, then regrow every 4 days, 3 berries x 50g.
    Planted by Su 15 -> at least 1 harvest; earlier = more harvests. Spend down to a 500g reserve."""
    s = sv.state()
    if s["season"] != "summer" or s["day"] > 14 or s["time"] >= 1630 or (s["day"] - 1) % 7 == 2:
        return
    act.goto("Farm", 64, 20)
    _, feats, _ = farming.tile_info(r=30)
    crops = sum(1 for f in feats.values() if f["type"] == "HoeDirt" and "crop" in f and not f.get("dead"))
    room = MAX_CROPS - crops
    money = s["player"]["money"]
    n = min(room, (money - 500) // 80)
    if n < 5:
        return
    act.log(f"summer money: buying {n} Blueberry Seeds ({crops} crops planted, {money}g)")
    town.open_shop("SeedShop")
    town.buy({"Blueberry Seeds": n})
    town.close_menu()
    act.goto("Farm", 64, 20)
    act.log(f"planted blueberries: {farming.replant('Blueberry Seeds')}, money {sv.state()['player']['money']}")

# Quality Crops (Parsnip option lost in spring): 5 gold Melon (summer) + 5 gold Pumpkin + 5 gold Corn (fall).
# Wiki: Basic Fertilizer (2 Sap, or Pierre 100g from Sp 15 Y1) -> 19-23% gold at Farming 4-5.
QUALITY_PUSH = {   # crop: (seed, season, first day, last planting day, target plants)
    "Parsnip": ("Parsnip Seeds", "spring", 1, 20, 30),   # Y2: 4 days, 5 gold needed (wiki Bundles)
    "Melon": ("Melon Seeds", "summer", 10, 16, 30),
    "Pumpkin": ("Pumpkin Seeds", "fall", 1, 15, 30),
    "Corn": ("Corn Seeds", "fall", 1, 14, 20),       # regrows every 4 days: many harvests per plant
}

def quality_push():
    s = sv.state()
    if s["time"] >= 1600 or (s["day"] - 1) % 7 == 2:
        return
    cc = needs.live() or {"bundles": []}
    qb = next((b for b in cc["bundles"] if b["name"] == "Quality Crops"), None)
    if not qb or qb["complete"]:
        return
    import craft, donate as D
    # feasible this year? need 3 of Parsnip/Melon/Pumpkin/Corn; spring/summer options are gone once their season ends
    order = ["spring", "summer", "fall", "winter"]
    reachable = 0
    for g in qb["ingredients"]:
        if g["done"]: reachable += 1; continue
        seasons_ok = {"Parsnip": ["spring"], "Melon": ["summer"], "Pumpkin": ["fall"], "Corn": ["summer", "fall"]}.get(g["name"], [])
        if any(order.index(x) >= order.index(s["season"]) for x in seasons_ok): reachable += 1
    if reachable < qb["slots"]:
        return                                   # not completable this year: no fertilizer spending
    for crop, (seed, season, d0, d1, target) in QUALITY_PUSH.items():
        if s["season"] != season or not (d0 <= s["day"] <= d1): continue
        if any(g["name"] == crop and g["done"] for g in qb["ingredients"]): continue
        p = prog(); key = f"gold_{crop.lower()}s" + (f"_y{s['year']}" if s["year"] > 1 else "")   # per-year target
        planted = p.get(key, 0)
        want = target - planted
        if want <= 0: continue
        price = {"Parsnip Seeds": 20, "Melon Seeds": 80, "Pumpkin Seeds": 100, "Corn Seeds": 150}[seed]
        money = sv.state()["player"]["money"]
        k = min(want, (money - 300) // (price + 100))      # + Pierre fertilizer 100g when Sap runs out
        if k < 6 and not (s["day"] >= d1 - 1 and k >= 1):
            continue
        fert = sum(i["stack"] for i in act.inv() if i["name"] == "Basic Fertilizer")
        if fert < k:
            if sum(i["stack"] for i in act.inv() if i["name"] == "Sap") < 2 * (k - fert):
                act.goto("Farm"); D.withdraw_bundle_items({"Sap", "Basic Fertilizer"})
            fert = sum(i["stack"] for i in act.inv() if i["name"] == "Basic Fertilizer")
            sap = sum(i["stack"] for i in act.inv() if i["name"] == "Sap")
            if fert < k and sap >= 2:
                craft.craft("Basic Fertilizer", n=min(k - fert, sap // 2))
        fert = sum(i["stack"] for i in act.inv() if i["name"] == "Basic Fertilizer")
        buy = {seed: k}
        if fert < k: buy["Basic Fertilizer"] = k - fert          # Pierre, 100g
        act.log(f"gold {crop}: buying {buy} (planted so far {planted}, money {money})")
        town.open_shop("SeedShop")
        town.buy(buy)
        town.close_menu()
        act.goto("Farm", 64, 24)
        held = sum(i["stack"] for i in act.inv() if i["name"] == seed)
        n = farming.plant_fertilized(seed, "Basic Fertilizer", held)
        p = prog(); p[key] = planted + n; save_prog(p)
        act.log(f"gold {crop}: planted {n} fertilized (total {planted + n})")

def melon_quality():
    quality_push()

def fall_money():
    """Wiki: Pumpkin Seeds 100g, 13 days, Pumpkin sells 320g -> two cycles in fall (Fa 1 and ~Fa 14).
    Better per day than Cranberries (240g, 7 days + 5-day regrow, 2 x 75g). Keep a 2,500g reserve; cap crops."""
    s = sv.state()
    if s["season"] != "fall" or s["day"] > 15 or s["time"] >= 1600 or (s["day"] - 1) % 7 == 2:
        return
    if 3 <= s["day"] <= 12: return            # buy on Fa 1-2, then replant ~Fa 13-15
    act.goto("Farm", 64, 24)
    _, feats, _ = farming.tile_info(r=30)
    crops = sum(1 for f in feats.values() if f["type"] == "HoeDirt" and "crop" in f and not f.get("dead"))
    import animals
    n = min(MAX_CROPS + 30 - crops, (s["player"]["money"] - 2500 - animals.upgrade_reserve()) // 100)
    if n < 5: return
    act.log(f"fall money: buying {n} Pumpkin Seeds ({crops} crops, {s['player']['money']}g)")
    town.open_shop("SeedShop"); town.buy({"Pumpkin Seeds": n}); town.close_menu()
    act.goto("Farm", 64, 24)
    act.log(f"planted pumpkins: {farming.replant('Pumpkin Seeds')}")

def farm_chores():
    act.goto("Farm", 64, 20)
    h = farming.harvest_all(); act.log(f"harvested {h}")
    _, feats, _ = farming.tile_info(r=60)
    left = [(t, f.get("crop")) for t, f in feats.items() if f["type"] == "HoeDirt" and f.get("ready")]
    if left:          # Fa 28: a ripe Yam and 15 Wheat stayed in the field unnoticed and died at the season change
        act.log(f"ERROR ripe crops left after harvest: {left[:10]}; emptying backpack and retrying once")
        # Su 17 Y2: backpack 24/24 -> Blueberries could not be picked; the per-tile retry right-clicked
        # them for 6 game hours. Free the backpack, then one more pass.
        chest_sync_and_ship()
        act.goto("Farm", 64, 20)
        act.log(f"harvest retry: {farming.harvest_all()}")
    farming.clear_dead()
    s = sv.state()
    for seed in seeds_in_inv():
        farming.replant(seed)
    if s["weather"] not in ("rain", "storm"):
        act.goto("Farm", 64, 24)                  # field centre: water_all scans a radius around the farmer
        act.log(f"watered {farming.water_all(r=28)}")

def cc_unlock(p):
    s = sv.state()
    if p.get("cc_cutscene") or s["day"] < 5 and s["season"] == "spring" or s["weather"] != "sun" or s["time"] >= 1230:
        return
    act.log("CC: entering Town from Bus Stop for Lewis cutscene (window 8:00-13:00, wiki)")
    act.goto("BusStop")
    while sv.state()["time"] < 800:          # forage while waiting for 8:00
        sv.call("turbo", sec=2, until=800)
        if town.forage_nearby(r=20, max_items=3) == 0:
            sv.call("hold", down=[sv.state()["keys"]["left"]]); time.sleep(0.3); sv.call("hold", up=[sv.state()["keys"]["left"]])
            time.sleep(0.5)
    act.goto("Town")
    for _ in range(200):
        s = act.dismiss()
        if s.get("free") and not s.get("event"): break
        time.sleep(0.4)
    p["cc_cutscene"] = True; save_prog(p)
    cc_scroll(p)

def cc_scroll(p):
    """Read the Golden Scroll in the lower-left room (note tile 14,23 — drawn on screen)."""
    if p.get("cc_scroll") or not p.get("cc_cutscene"):
        return
    act.goto("CommunityCenter")
    act.walk(14, 23, adjacent=True)
    act.use(14, 23, right=True)
    act.dismiss()
    import town; town.close_menu()
    p["cc_scroll"] = sv.state()["day"]; save_prog(p)
    act.log("CC: read golden scroll")

def wizard(p):
    """Day after the scroll: visit the Wizard (tower in west Forest) -> bundles unlock."""
    s = sv.state()
    if p.get("wizard") or not p.get("cc_scroll") or p["cc_scroll"] == s["day"]:
        return
    act.log("visiting Wizard")
    act.goto("WizardHouse")
    for _ in range(200):
        st = act.dismiss()
        if st.get("free") and not st.get("event"): break
        time.sleep(0.4)
    p["wizard"] = True; save_prog(p)

def forage_tour():
    # forage only every 2nd day (spawns are sparse when picked daily; walking costs 2+ game hours),
    # and only when a bundle still needs forage of this season (Sp 18: 2 hours for 0 items)
    s = sv.state()
    if (s["day"] % 2 and s["season"] != "winter") or s["time"] >= 1800: return
    season_forage = {"spring": town.SPRING_FORAGE, "summer": town.SUMMER_FORAGE, "fall": town.FALL_FORAGE, "winter": town.WINTER_FORAGE}.get(s["season"], set())
    q = set(needs.quota())
    skip = {"Morel"} if s["season"] != "fall" else set()          # Common Mushroom spawns on fall maps (wiki)
    want = (season_forage - skip - ({"Common Mushroom"} if s["season"] != "fall" else set())) & q
    hold = needs.quality_holds()
    spare_fruit = [i for i in act.inv() if i.get("cat") == -79 and i["name"] not in q
                   and not (i["name"] in hold and i.get("quality", 0) >= hold[i["name"]][0])]
    if False and "Wine" in q and prog().get("keg") and s["season"] == "winter" and not spare_fruit:
        # disabled W27: tours cost ~4 game hours/day for <= 1 Crystal Fruit, which was then eaten or shipped
        want |= {"Crystal Fruit"}          # W21: the keg had no fruit; Crystal Fruit is winter forage fruit (wiki)
    # beach forage, any season. Sea Urchin only spawns east of the broken footbridge (wiki Sea Urchin; repair = 300
    # Wood) except Su 12-14: W1-W3 tours walked to the Beach for it every day and found 0
    beach = {"Cockle", "Oyster", "Nautilus Shell", "Coral"} & q
    if "Sea Urchin" in q and s["season"] == "summer" and 12 <= s["day"] <= 14: beach.add("Sea Urchin")
    if not want and not beach:
        act.log("forage tour skipped: no bundle needs in-season forage"); return
    maps = {"summer": ["BusStop", "Mountain", "Forest"], "fall": ["Forest", "Mountain", "BusStop"],
            "winter": ["Forest", "Mountain", "BusStop", "Town"]}.get(s["season"], ["Mountain", "Beach"]) if want else []
    if beach and "Beach" not in maps: maps.append("Beach")
    act.log(f"forage tour for {sorted(want | beach)}: {maps}")
    for loc in maps:
        try:
            act.goto(loc); n = town.forage_nearby(r=40, max_items=25); act.log(f"{loc}: {n} foraged")
            if s["season"] == "winter" and {"Winter Root", "Snow Yam"} & q:
                town.dig_artifact_spots(r=40)
                owned = {i["name"] for i in act.inv()} | {k for k, v in (prog().get("chest") or {}).items() if v}
                if ({"Winter Root", "Snow Yam"} & set(needs.quota())) - owned:
                    town.till_for_roots(n=30)
        except Exception as e:
            act.log(f"forage {loc} failed: {e}")
        if sv.state()["time"] > 1700: break

def clear_routes():
    """One-time: clear debris along house->exits so every later trip walks a free path."""
    p = prog()
    done = set(p.get("routes_cleared", []))
    s = sv.state()
    if s["player"]["stamina"] < 150:
        return
    act.goto("Farm")
    for dest in ("BusStop", "Forest"):
        if dest in done: continue
        w = next((w for w in act.world()["Farm"] if w["to"] == dest), None)
        if not w: continue
        a = sv.call("around", r=1)
        goal = (min(max(w["x"], 0), a["w"] - 1), min(max(w["y"], 0), a["h"] - 1))
        act.walk(64, 16)
        ok = farming.clear_path_to(goal, debris_cost=1.3)     # prefer clearing debris over a long detour
        act.log(f"route to {dest} cleared: {ok}")
        if ok:
            done.add(dest); p["routes_cleared"] = sorted(done); save_prog(p)
        act.walk(64, 16)

def donate():
    p = prog()
    if not p.get("wizard"):
        return
    import donate as D
    D.donate_all(p.get("chest", {}))

MINIMAL = os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "MINIMAL"))

def cc_needs_outing():
    """Minimal mode: go fishing/mining only when a bundle still needs a fish biting now or a mine item."""
    s = sv.state(); q = set(needs.quota())
    if s["weather"] in ("rain", "storm"): return True
    import fishplan
    fishb = {"River Fish", "Lake Fish", "Ocean Fish", "Night Fishing", "Specialty Fish", "Crab Pot"}
    cc = needs.live() or {"bundles": []}
    want = [g["name"] for b in cc["bundles"] if b["name"] in fishb and not b["complete"] for g in b["ingredients"] if not g["done"]]
    if fishplan.plan(want, s["season"], s["weather"], max(s["time"], 600)): return True
    if "Maki Roll" in q and not any(i["name"] == "Seaweed" for i in act.inv()): return True
    return bool({"Quartz", "Earth Crystal", "Frozen Tear", "Fire Quartz", "Aquamarine", "Ghostfish", "Slime", "Bat Wing",
                 "Void Essence", "Solar Essence", "Frozen Geode"} & q)

def morning_care():
    """Sp 11 Y2: at midday the hungry hens crowd the bench and it cannot be reached; feed them at 6:00 instead."""
    try:
        import animals
        animals.care("Coop"); animals.care("Barn")
    except Exception as e:
        act.log(f"morning care failed: {e!r}")

def _mins(t): return (t // 100) * 60 + t % 100

def sanity_step_time(step, t0):
    """Sanity watchdog: a step that eats > 3 game hours is logged (Su 17 Y2: harvest retry ate 6 hours unnoticed)."""
    try:
        dt = _mins(sv.state()["time"]) - _mins(t0)
        name = getattr(step, "__name__", "step")
        if dt > 180 and name not in ("mining_or_fishing", "use_leftover_time", "morning_fish", "desert_trip", "evening"):
            act.log(f"SANITY: step {name} took {dt} game minutes")
    except Exception:
        pass

def day_audit(s0):
    """End-of-day sanity audit: things a player would notice."""
    try:
        s = sv.state(); inv = s.get("inventory") or []
        ch = prog().get("chest") or {}
        notes = []
        if len(inv) >= s.get("backpack", 12): notes.append(f"backpack FULL ({len(inv)})")
        nm = prog().get("chest_main_names", len(ch))
        if nm >= 33: notes.append(f"main chest nearly full ({nm} item types)")
        dm = s["player"]["money"] - s0["player"]["money"]
        if dm < -3000: notes.append(f"money {dm:+}g today")
        if s["player"]["money"] < 500: notes.append(f"money low {s['player']['money']}g")
        if s["time"] < 1800: notes.append(f"bed at {s['time']} (day unused)")
        import cc_progress
        _, _, sl, _ = cc_progress.progress()
        p = prog(); hist = p.setdefault("slots_hist", [])
        if sl is not None:
            hist.append(sl); p["slots_hist"] = hist[-14:]; save_prog(p)
            if len(hist) >= 7 and hist[-1] == hist[-7]: notes.append(f"CC slots unchanged for 7 days ({sl})")
        act.log("AUDIT: " + ("; ".join(notes) if notes else "ok"))
    except Exception as e:
        act.log(f"AUDIT failed: {e!r}")

def wood_needed():
    """Wood still needed for planned builds (Fa 18 Y2: 7 Wood held, ~1,250 needed; Robin sells at 50g in Y2)."""
    import needs, animals
    q = set(needs.quota()); p = prog(); need = 0
    if "Truffle" in q:
        if not p.get("big_barn"): need += animals.SPEC["Big Barn"]["wood"]
        if not p.get("deluxe_barn"): need += animals.SPEC["Deluxe Barn"]["wood"]
    if ("Duck Feather" in q or "Rabbit's Foot" in q) and not p.get("big_coop"): need += animals.SPEC["Big Coop"]["wood"]
    if "Rabbit's Foot" in q and not p.get("deluxe_coop"): need += animals.SPEC["Deluxe Coop"]["wood"]
    if "Sea Urchin" in q and not p.get("beach_bridge"): need += 300
    have = sum(i["stack"] for i in act.inv() if i["name"] == "Wood") + (p.get("chest") or {}).get("Wood", 0)
    return max(0, need - have)

def stone_needed():
    import needs, animals
    q = set(needs.quota()); p = prog(); need = 0
    if "Truffle" in q and not p.get("deluxe_barn"): need += animals.SPEC["Deluxe Barn"]["stone"]
    if ("Duck Feather" in q or "Rabbit's Foot" in q) and not p.get("big_coop"): need += animals.SPEC["Big Coop"]["stone"]
    if "Rabbit's Foot" in q and not p.get("deluxe_coop"): need += animals.SPEC["Deluxe Coop"]["stone"]
    have = sum(i["stack"] for i in act.inv() if i["name"] == "Stone") + (p.get("chest") or {}).get("Stone", 0)
    return max(0, need - have)

def stone_step():
    """Amer: wood and stone come from trees and rocks. Break farm rocks while builds need Stone."""
    n = stone_needed()
    if n <= 0 or sv.state()["player"]["stamina"] < 50: return
    act.goto("Farm", 64, 24)
    got = 0
    for _ in range(40):
        if stone_needed() <= 0 or sv.state()["player"]["stamina"] < 40 or sv.state()["time"] >= 2300: break
        a = sv.call("around", r=50); _, me = act.here()
        rocks = [o for o in a["objects"] if o["name"] == "Stone"]
        if not rocks: break
        o = min(rocks, key=lambda o: abs(o["x"] - me[0]) + abs(o["y"] - me[1]))
        if farming.approach((o["x"], o["y"])) != "arrived": continue
        for _ in range(3): act.use(o["x"], o["y"], tool="Pickaxe")
        farming.collect_debris(r=3); got += 1
    act.log(f"stone: broke {got} rocks (still need {stone_needed()})")

def wood_step():
    """Chop farm trees with spare energy while builds still need Wood (free; trees also wall off paths)."""
    n = wood_needed()
    if n <= 0: return
    s = sv.state()
    if s["player"]["stamina"] < 60: return
    act.goto("Farm", 70, 18)
    held = sum(i["stack"] for i in act.inv() if i["name"] == "Wood")
    # morning pass keeps ~half the energy for the mines; the evening pass uses what is left
    floor = 40 if sv.state()["time"] >= 1600 else max(40, s["player"]["max_stamina"] // 2 if "max_stamina" in s["player"] else 130)
    got = farming.chop_trees(wood_target=held + n, min_stamina=floor, r=40)
    act.log(f"wood: chopped to {got} (still need {wood_needed()})")

def maki_step():
    import cook
    try: cook.step()
    except Exception as e: act.log(f"maki step failed: {e!r}")
    finally:
        try: town.close_menu()
        except Exception: pass

def beach_step():
    import beach
    try: beach.tide_pools()
    except Exception as e: act.log(f"beach step failed: {e!r}")

def fruit_step():
    """Session 6: Apple (Fodder) and Pomegranate (Enchanter's) saplings; deadline Su 25 / Su 27 (fruit.py)."""
    import fruit
    try: fruit.pick()
    except Exception as e: act.log(f"fruit pick failed: {e!r}")
    try: fruit.keep_clear()
    except Exception as e: act.log(f"fruit keep_clear failed: {e!r}")
    fruit.buy_and_plant()

def silo_step():
    """Sp 3 Y2: spring chores ran until 18:00, past Robin's hours; the silo (hoppers feed the hens) goes first."""
    try:
        import animals; animals.build_silo()
    except Exception as e:
        act.log(f"silo step failed: {e!r}")

def animals_step():
    """Coop + chickens (agent/animals.py): Animal bundle Large Eggs, Y2 speed."""
    try:
        sv.call("animal_menu")            # older mod build has no animal/carpenter endpoints
    except Exception:
        return
    import animals; animals.run()

def mining_or_fishing():
    s = sv.state(); p = prog()
    if s["weather"] in ("rain", "storm"):
        fishing(until=2130); return
    # summer/fall: seasonal bundle fish can't wait; fish every other sunny day while any is biting today
    # (Su 9: every sunny day while a seasonal bundle fish is still missing; mining is weak with the Rusty Sword)
    if s["season"] in ("summer", "fall"):
        import fishplan
        fishb = {"River Fish", "Lake Fish", "Ocean Fish", "Night Fishing", "Specialty Fish"}
        cc = needs.live() or {"bundles": []}
        want = [g["name"] for b in cc["bundles"] if b["name"] in fishb and not b["complete"] for g in b["ingredients"] if not g["done"]]
        pl = fishplan.plan(want, s["season"], "sun", max(s["time"], 900)) or fishplan.plan(want, s["season"], "sun", 1300)   # Pufferfish 12-16
        if pl:
            act.log(f"fishing day (seasonal bundle fish): {pl[:2]}")
            fishing(until=2130); return
    winter = s["season"] == "winter"          # no crops: the whole day goes to the mines (Geologist's, Adventurer's, Frozen Geode, Aquamarine)
    has_pick = any("Pickaxe" in i["name"] for i in act.inv())     # upgrade days: pickaxe is at Clint's
    if not has_pick and prog().get("pick_ready_day") is not None:
        # W2: the morning projects pass ran at 7:40, before Clint opens (9:00): fetch the pickaxe now
        try:
            import projects; projects.upgrade_pickaxe()
        except Exception as e:
            act.log(f"pickaxe pickup failed: {e!r}")
        has_pick = any("Pickaxe" in i["name"] for i in act.inv())
        s = sv.state()
    if has_pick and s["time"] < (2000 if winter else 1600) and (s["season"] != "spring" or s["day"] >= 5) and s["player"]["stamina"] >= 80 and s["player"]["health"] >= 60 and p.get("mine_days", 0) < 99:
        import mining
        # come prepared: empty the backpack into the chest so ore/stone/geodes fit (Amer spotted full-pack mining)
        free = s.get("backpack", 12) - len(act.inv())
        if free < 6:
            act.log(f"only {free} free slots before mining: emptying to chest")
            chest_sync_and_ship()
        try:
            t = sv.state()["time"]                # Specialty Fish; then mine on from floor 20 (2 game hours max)
            if winter and t < 1900: mining.ghostfish(until_time=min(2000, max(1300, t + 200)))
        except Exception as e:
            act.log(f"ghostfish failed: {e!r}")
        n = mining.run(max_levels=40 if winter else 10, until_time=2100 if winter else 1830)
        st2 = sv.state()
        if winter and st2["time"] < 1700 and st2["player"]["stamina"] > 80 and st2["player"]["health"] > 50:
            act.log(f"mine left early ({st2['time']}): second run from the lift")   # W13: fished from 13:30 instead
            n += mining.run(max_levels=40, until_time=2100)
        try:
            import guild; guild.visit()             # better weapon when floors unlock and money allows
        except Exception as e:
            act.log(f"guild visit failed: {e!r}")
        p = prog(); p["mine_days"] = p.get("mine_days", 0) + 1; save_prog(p)
        act.log(f"mined {n} levels")
    else:
        fishing(until=2100)
    # never go to bed early: use leftover hours (fishing costs little stamina)
    s = sv.state()
    if s["time"] < 1900 and s["player"]["stamina"] > 25:
        act.log("time left: fishing")
        fishing(until=2130)

def fishing(until=2100):
    """Rain: Forest river (Catfish/Shad rain fish). Sun: Mountain lake. (wiki fish locations)
    Keeps moving to new spots until `until` or out of energy: a dead spot must not end the day."""
    s = sv.state()
    if s["player"]["stamina"] < 40: return
    if s.get("backpack", 12) - len(act.inv()) < 4:
        chest_sync_and_ship()
    import fishplan
    fishb = {"River Fish", "Lake Fish", "Ocean Fish", "Night Fishing", "Specialty Fish", "Crab Pot"}
    cc = needs.live() or {"bundles": []}
    want = [g["name"] for b in cc["bundles"] if b["name"] in fishb and not b["complete"] for g in b["ingredients"] if not g["done"]]
    pl = fishplan.plan(want, s["season"], s["weather"], s["time"], exclude={FESTIVAL_MAP})
    act.log(f"fish plan {s['time']}: {pl[:3]}")
    places = []
    for p in [m for m, _ in pl] + ["Mountain", "Town", "Forest"]:
        if p not in places and p != FESTIVAL_MAP:
            places.append(p)
    if "Maki Roll" in needs.quota() and not any(i["name"] == "Seaweed" for i in act.inv()) and FESTIVAL_MAP != "Beach":
        places = ["Beach"] + [p for p in places if p != "Beach"]     # Seaweed = ocean fishing (wiki), for Maki Roll
    tried = {p: [] for p in places}
    productive = set()
    for _ in range(12):
        s = sv.state()
        if s["player"]["stamina"] < 25:
            import mining; mining.eat_if_tired(25); s = sv.state()
        if s["time"] >= until - 30 or s["player"]["stamina"] < 25:
            return
        if s.get("backpack", 12) - len(act.inv()) < 4:
            chest_sync_and_ship()
        # re-plan every round: fish windows close (Tilapia 14:00, Pufferfish 16:00) and another map may be better
        pl = fishplan.plan(want, s["season"], s["weather"], s["time"], exclude={FESTIVAL_MAP})
        if not pl:      # session 6: nothing wanted bites yet -> wait at the map of the next wanted window (Pufferfish 12:00 Beach)
            fw = fishplan.facts(want); h0 = s["time"] // 100
            nxt = sorted({a for n in want for a, b in (fw.get(n) or {}).get("windows", []) if h0 < a < until // 100})
            for a in nxt:
                pl = fishplan.plan(want, s["season"], s["weather"], a * 100, exclude={FESTIVAL_MAP})
                if pl: pl = [(m, []) for m, _ in pl]; break
        for m, _ in pl:      # maps that start biting later in the day were missing from `places` (Su 1 Y2: no Beach)
            tried.setdefault(m, [])
        order = [m for m, _ in pl] + [p for p in places if p not in [m for m, _ in pl]]
        place = next((p for p in order if len(tried.setdefault(p, [])) < 3), None)
        targets = dict(pl).get(place, [])
        f = fishplan.facts(targets)
        h = s["time"] // 100
        ends = [b for n in targets for a, b in (f.get(n) or {}).get("windows", []) if a <= h < b]
        session_until = min(until, max(ends) * 100) if ends else until
        if not targets:      # nothing wanted bites yet: fish here only until the next wanted window opens
            fw = fishplan.facts(want)
            starts = [a for n in want for a, b in (fw.get(n) or {}).get("windows", [])
                      if a > h and fishplan.biting(fw[n], s["season"], s["weather"], a * 100)]
            if starts: session_until = min(session_until, min(starts) * 100)
        if not place:
            act.log("fishing: every spot tried"); return
        if sv.state()["time"] >= session_until - 30:   # Sp 8 fresh save: walked to the Beach at 21:40 for a session ending 21:30
            act.log(f"fishing: too late for a session ending {session_until}"); return
        act.goto(place)
        # spots that produced fish this session may be reused (a fresh bank search often lands on shore)
        known = [tuple(t) for t in prog().get("fish_spots", {}).get(place, []) if tuple(t) not in tried[place] or tuple(t) in productive]
        if known and act.walk(*known[0]) == "arrived":
            act.log(f"fishing: known good spot {known[0]} at {place}")
        else:
            _, me = act.here()
            if not daily.go_fish_spot_near(me[0], me[1] + 8, r=40, tries=10, exclude=tried[place]):
                act.log(f"fishing: no spot found at {place}"); tried[place] += [(-99, -99)] * 3; continue
        spot = act.here()[1]
        tried[place].append(spot)
        try:
            caught0 = sv.state()["fish"]["catches"]
            act.log(f"fishing at {place} for {targets or 'anything'} until {session_until}")
            daily.fish_session(until_time=session_until, min_stamina=20)
            if sv.state()["fish"]["catches"] > caught0:      # remember spots that really produce fish
                p = prog(); spots = p.setdefault("fish_spots", {}).setdefault(place, [])
                productive.add(tuple(spot))
                if list(spot) not in spots:
                    spots.insert(0, list(spot)); save_prog(p); act.log(f"fishing: saved good spot {spot} at {place}")
        except LookupError as e:
            act.log(f"fishing: {e}")

def use_leftover_time():
    """Never sleep early (lesson 22): fish while there is time and energy."""
    s = sv.state()
    if s["time"] < 1900 and s["player"]["stamina"] > 40:
        act.log(f"leftover time at {s['time']}: fishing")
        fishing(until=2130)

def morning_fish():
    """Morning-only bundle fish (Tilapia 6:00-14:00, wiki) were missed because fishing started after noon.
    If one is still needed and biting now, fish first; shops/donations follow."""
    s = sv.state()
    if s["weather"] in ("rain", "storm") or s["time"] >= 1100: return
    import fishplan
    fishb = {"River Fish", "Lake Fish", "Ocean Fish", "Night Fishing", "Specialty Fish"}
    cc = needs.live() or {"bundles": []}
    want = [g["name"] for b in cc["bundles"] if b["name"] in fishb and not b["complete"] for g in b["ingredients"] if not g["done"]]
    f = fishplan.facts(want)
    morning = [n for n in want if f.get(n) and any(fishplan.biting(f[n], s["season"], s["weather"], t) for t in (s["time"], 1230))
               and all(b <= 16 for a, b in f[n]["windows"])]
    if morning:
        act.log(f"day-window fish first: {morning}")
        fishing(until=max(b for n in morning for a, b in f[n]["windows"]) * 100)

def desert_trip():
    import desert; desert.trip()

def woods_visit():
    import woods; woods.visit()

def cart_visit():
    import cart; cart.visit()

def projects_run():
    import projects; projects.run()

def evening_wood():
    """Construction bundle: Wood 99 x2 (wiki). Spare evening energy goes into farm trees near the house."""
    s = sv.state()
    q = needs.quota()
    if "Wood" not in q or s["time"] >= 2300 or s["player"]["stamina"] < 70:
        return
    chest = prog().get("chest", {}).get("Wood", 0)
    target = q["Wood"] - chest
    if target <= 0:
        return
    act.goto("Farm", 64, 20)
    import farming
    held = sum(i["stack"] for i in act.inv() if i["name"] == "Wood")
    w = farming.chop_trees(wood_target=min(held + target, held + 60), min_stamina=40)
    act.log(f"evening wood: holding {w} (chest {chest}, bundle wants {q['Wood']})")

def evening():
    try:
        import animals; animals.collect_truffles()
    except Exception as e:
        act.log(f"truffles failed: {e!r}")
    try:
        import projects
        if sv.state()["time"] < 2300: projects.smelt()
    except Exception as e:
        act.log(f"evening smelt failed: {e!r}")
    chest_sync_and_ship()
    daily.stats_row("day end")

def festival_day(fest):
    global FESTIVAL_MAP
    import festivals
    act.log(f"FESTIVAL: {fest[0]}")
    if os.path.exists(os.path.join(os.path.dirname(__file__), "ANIMALS")):
        # W25 Y2: the festival branch ignored ANIMALS mode (no animal care, a mine trip that ate every egg)
        FESTIVAL_MAP = fest[1]
        # Sp 24 Y3: animals_step walked into the Forest during the Flower Dance (stuck in the festival map). Marnie
        # is closed on festival days (wiki); the cart and the CC trip can cross the festival map too: farm only.
        for step in (daily.read_mail, morning_care, chest_sync_and_ship, evening):
            try: step()
            except Exception as e: act.log(f"STEP FAILED {getattr(step,'__name__','step')}: {e!r}")
        town.sleep_and_wake(); daily.stats_row("new day"); return
    for step in (daily.read_mail, farm_chores):
        try: step()
        except Exception as e: act.log(f"STEP FAILED {step.__name__}: {e!r}")
    if fest[0] == "Egg Festival":
        festivals.egg_festival()
        town.sleep_and_wake(); daily.stats_row("new day"); return
    # no routine for this festival yet: play a normal day, but keep away from the festival map
    FESTIVAL_MAP = fest[1]
    act.log(f"no routine for {fest[0]}: normal day, avoiding {fest[1]}")
    for step in (clear_routes, chest_sync_and_ship, donate, buy_seeds, mining_or_fishing, use_leftover_time, evening):
        try: step()
        except Exception as e: act.log(f"STEP FAILED {getattr(step,'__name__','step')}: {e!r}")
    town.sleep_and_wake(); daily.stats_row("new day")

FESTIVAL_MAP = None

def main():
    try:      # optional speed override (agent/SPEED file), e.g. 12; the mod caps at 16
        sp = int(open(os.path.join(os.path.dirname(__file__), "SPEED")).read().strip())
        # session 5: headless turbo (Amer: no need to watch; videos still saved from the timelapse frames)
        sv.call("speed", n=sp, headless=sp > 16, draw_every=60)
    except Exception:
        pass
    m = (sv.state().get("menu") or {}).get("type")
    if m in act._STRAY:            # Fa 5 Y2: the shipping screen was still open at 6:00; every walk failed
        act.log(f"SANITY: {m} open at day start: closing")
        for _ in range(10):
            try:
                if not town.close_menu(): pass
                break
            except RuntimeError:
                sv.call("turbo", sec=2); act.dismiss(); time.sleep(1)
    p = prog()
    s = sv.state()
    import calendar_sv
    fest = calendar_sv.today(s["season"], s["day"])
    global FESTIVAL_MAP
    if fest and fest[2] >= 2200:
        # evening festival (Jellies 22:00, Spirit's Eve 22:00): full normal day; fishing ends 21:30, before it starts
        act.log(f"evening festival {fest[0]} at {fest[1]}: normal day, {fest[1]} closed until then")
        act.CLOSED = {fest[1]}
    elif fest:
        return festival_day(fest)
    act.log(f"=== DAY START Y{s['year']} {s['season']} {s['day']} weather {s['weather']} money {s['player']['money']} ===")
    try:
        import cc_progress
        d_, n_, f_, s_ = cc_progress.progress()
        act.log(f"CC progress: {d_}/{n_} bundles, {f_}/{s_} slots")
        if d_ >= n_:
            act.log("CC COMPLETE: stopping the loop after today")
            # DONE, not STOP: play.sh deletes STOP at start, so a restarted loop kept playing (LESSONS 154)
            open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "DONE"), "w").close()
    except Exception as e:
        act.log(f"cc progress check failed: {e!r}")
    try:
        import seasons
        urgent, soon = seasons.deadlines(s["season"], s["day"])
        act.log(f"SEASON DEADLINES: urgent {[(u['item'], u['bundle']) for u in urgent]}; next season {sorted({x['item'] for x in soon})}")
        json.dump({"date": [s["year"], s["season"], s["day"]], "urgent": urgent, "next": soon},
                  open(os.path.join(os.path.dirname(STATE_FILE), "..", "stats", "deadlines.json"), "w"), indent=1)
    except Exception as e:
        act.log(f"deadline check failed: {e!r}")
    daily.stats_row("day start")
    day0 = (s["season"], s["day"]); s_day0 = s
    for step in (daily.read_mail, morning_care, farm_chores, fruit_step, maki_step, silo_step, clear_routes, chest_sync_and_ship, cart_visit, melon_quality, projects_run, morning_fish, lambda: cc_unlock(p), lambda: cc_scroll(p), lambda: wizard(p), donate, animals_step, buy_bundle_seeds, buy_seeds, summer_money, fall_money, woods_visit, desert_trip, forage_tour, wood_step, beach_step, mining_or_fishing, stone_step, wood_step, use_leftover_time, evening_wood, evening):
        st = sv.state()
        if (st["season"], st["day"]) != day0:
            act.log("DAY CHANGED during the day (passed out?): no more steps, no sleep")
            daily.stats_row("new day"); return
        if st["time"] >= 2300 and step is not evening:
            continue                          # late: only the evening ship/chest step, then bed (Su 5-6 pass-outs)
        # Amer W18 Y2: only animal products left (Large Egg, Truffle, Duck Feather, Rabbit's Foot): pet, feed,
        # ship, check the cart, donate, buy animal upgrades when affordable, sleep. File agent/ANIMALS turns it on.
        if os.path.exists(os.path.join(os.path.dirname(__file__), "ANIMALS")) and step not in (
                daily.read_mail, morning_care, chest_sync_and_ship, cart_visit, donate, animals_step, wood_step, stone_step, evening):
            continue
        if MINIMAL and step in (clear_routes, woods_visit, use_leftover_time, evening_wood):
            continue                          # session 5 (Amer): bare minimum for the CC, sleep the rest of the day
        if MINIMAL and step is mining_or_fishing and not cc_needs_outing():
            act.log("minimal: no bundle fish or mine item needed today: straight to evening/bed"); continue
        if st["time"] >= 2400 and step is evening:
            act.log("past midnight: skipping evening, straight to bed"); continue
        act._NP[0] = 0
        act.NP_CHECK[0] = step not in (morning_care, animals_step)
        t0 = st["time"]
        try:
            step()
            sanity_step_time(step, t0)
        except Exception as e:
            import traceback; act.log(f"STEP FAILED {getattr(step,'__name__','step')}: {e!r} @ {traceback.format_exc().splitlines()[-3].strip()}"); print("".join("    " + l for l in traceback.format_exc().splitlines(True)[-14:]), flush=True)
            try:
                sv.call("stop"); act.reel_in()
                for _ in range(80):                 # cutscenes (e.g. Special Orders, Fa 2) stop steps: click through
                    st2 = act.dismiss()
                    if st2.get("free") and not st2.get("event"): break
                    time.sleep(0.3)
                if sv.state().get("menu") and sv.state()["menu"]["type"] not in ("GameMenu",):
                    town.close_menu()
            except Exception as e2:
                act.log(f"recovery after step failure failed: {e2!r}")
            # Su 3 Y2: one failed walk ended the outing at 8:40 and the farmer slept at 9:10. Retry once.
            # any step (fresh save, Sp 7: leaving the house at 6:00 timed out once): retry once after recovery
            if step is not evening and sv.state()["time"] < 1700:
                act.log(f"retrying {getattr(step,'__name__','step')} once")
                try: step()
                except Exception as e3: act.log(f"STEP FAILED again {getattr(step,'__name__','step')}: {e3!r}")
    st = sv.state()
    if (st["season"], st["day"]) != day0:
        act.log("DAY CHANGED before bed (passed out?): not sleeping again")
    else:
        day_audit(s_day0)
        town.sleep_and_wake()
    daily.stats_row("new day")

if __name__ == "__main__":
    act.run(main)
