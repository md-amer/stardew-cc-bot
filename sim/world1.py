"""World v1: the day is an agenda of tasks run on a real clock (6:00-2:00) with locations, travel (travel.json
from the game maps), opening hours (map door data + wiki closed days), fish hours (Data/Fish), and the TV
forecast (tomorrow's weather known each night). The nightly planner (planner.py) writes the agenda.
Subsystems (crops, animals, bundles, mining, cart, bats) are inherited from world.py (v0).
"""
import json, os, math
import world as W
import gamedata as g

HERE = os.path.dirname(os.path.abspath(__file__))
TRAVEL = {tuple(k.split("|")): v for k, v in json.load(open(os.path.join(HERE, "data", "travel.json"))).items()}
OPEN = {"pierre": (900, 1700), "clint": (900, 1600), "robin": (900, 1700), "marnie": (900, 1600), "willy": (900, 1700),
        "gus": (1200, 2400), "cc": (600, 2600), "cart": (600, 2000), "busstop": (1000, 2400), "museum": (800, 1800)}
CLOSED = {"pierre": {2}, "robin": {1}, "marnie": {0, 1}, "willy": {5}}   # dow 0=Mon (Willy: sunny Saturdays)
SPOT_PLACE = {("Mountain", None): "mountain_lake", ("Forest", "River"): "forest_river", ("Forest", "Lake"): "forest_river",
              ("Town", "River"): "town_river", ("Beach", "Default"): "beach", ("Woods", None): "woods",
              ("Desert", "TopPond"): "busstop", ("Backwoods", None): "backwoods", ("UndergroundMine", None): "mine"}


def clock_add(t, mins):
    m = (t // 100) * 60 + t % 100 + mins
    return int(m // 60) * 100 + int(m % 60)


def cmin(t): return (t // 100) * 60 + t % 100


PLACE_FORAGE = {"forest_river": "Forest", "mountain_lake": "Mountain", "town_river": "Town", "beach": "Beach",
                "busstop": "BusStop", "woods": "Woods", "cart": "Forest", "pierre": "Town", "gus": "Town", "clint": "Town"}


class Task:
    def __init__(self, name, place, dur, energy=0, earliest=600, latest=2600, run=None, min_dur=None):
        self.name, self.place, self.dur, self.energy = name, place, dur, energy
        self.earliest, self.latest, self.run = earliest, latest, run
        self.min_dur = min_dur if min_dur is not None else dur
    def __repr__(self): return f"{self.name}@{self.place}"


class World1(W.World):
    def __init__(self, plan, speeds=W.BOT, seed=0, planner=None, walk_factor=1.5):
        super().__init__(plan, speeds, seed)
        self.walk_factor = walk_factor
        import planner as P
        self.planner = planner or P.Rolling()
        self.forecast = self.weather_for(0)
        self.watered_today = False
        self.agenda_log = []
        self.prof = set()
        # Speeds.overhead (bot 283 game min/day 'other') split into per-stop and morning overheads
        self.stop_overhead = speeds.overhead * 10 / 283
        self.morning_overhead = speeds.overhead * 30 / 283
        self.target_energy_reserve = 100

    def weather_for(self, t):
        keep = self.t; self.t = t; w = self.weather(); self.t = keep; return w

    def open_today(self, place):
        if place in CLOSED and self.dow() in CLOSED[place]:
            if place == "willy" and self.w == "rain": return True
            return False
        if self.festival() and place in OPEN and place not in ("cc", "cart"): return False
        return True

    def day(self):
        self.w = self.forecast                      # today's weather was forecast last night
        self.luck = self.r.randint(-100, 100) / 1000
        self.watered_today = False
        self.overnight()
        self.plant_today()
        self.extra_reserve = self.seed_budget()
        agenda = self.planner.plan(self)
        clock, loc, energy = clock_add(600, self.morning_overhead), "bed", 270
        energy_cap = 270
        done = []
        overhead = self.s.overhead
        for task in agenda:
            if not self.open_today(task.place) and task.place in OPEN and task.place not in ("cc",): continue
            travel = TRAVEL.get((loc, task.place), 30) * self.walk_factor
            start = clock_add(clock, travel)
            o = OPEN.get(task.place)
            earliest = max(task.earliest, o[0] if o else 600)
            latest = min(task.latest, o[1] if o else 2600)
            if cmin(start) < cmin(earliest): start = earliest
            if task.place == "busstop" and cmin(start) > cmin(1700): continue   # must board the bus by 17:00
            start = clock_add(start, self.stop_overhead)
            avail = cmin(min(latest, 2600)) - cmin(start)
            if avail < task.min_dur: continue
            dur = min(task.dur, avail)
            if task.energy:
                dur = min(dur, task.dur * max(0, energy) / task.energy)
                if dur < task.min_dur: continue
            used = task.run(self, dur) if task.run else dur
            floc = PLACE_FORAGE.get(task.place)
            if floc and self.forage.get(floc):
                for i in self.forage[floc]: self.add(i); self.xp["foraging"] += 7
                self.forage[floc] = []
            used = dur if used is None else used
            energy -= task.energy * (used / max(task.dur, 1))
            clock = clock_add(start, used); loc = task.place
            done.append(task.name)
        self.agenda_log.append((self.t, done))
        self.end_of_day()
        self.forecast = self.weather_for(self.t + 1)

    # ---------- task bodies (return minutes actually used)
    def do_water(self, dur):
        self.watered_today = True; return dur

    def do_animals(self, dur): return dur

    def do_cc(self, dur):
        self.donate(); self.pay_vault()
        if self.room_done("Vault") and "bus" not in self.buildings: self.buildings["bus"] = self.t + 1
        return 10

    def do_shop(self, dur):
        self.purchases(); return 15

    def do_gus(self, dur):
        nd = self.needed()
        if "Maki Roll" in nd and self.gold >= 300 + self.res(): self.gold -= 300; self.add("Maki Roll")
        if "Fried Egg" in nd and self.r.random() < 1 / 41 and self.gold >= 400: self.gold -= 400; self.add("Fried Egg")
        return 5

    def do_cart(self, dur): self.cart(); return 10

    def can_handin(self):
        nd = self.needed()
        for b, v in self.slots.items():
            if b in self.done: continue
            for k, (nm, q, ql) in enumerate(v["items"]):
                if k in v["got"]: continue
                key = nm + ("*" if ql == 2 else "")
                if nm != "gold" and self.inv.get(key, 0) >= q: return True
        nxt = next((b for b in ("2,500g", "5,000g", "10,000g", "25,000g") if b not in self.done), None)
        return bool(nxt) and self.gold - int(nxt.replace(",", "").replace("g", "")) >= self.res()

    def do_clint(self, dur):
        """axe upgrades for Secret Woods: copper axe (2000g + 5 copper bars), then steel axe (5000g + 5 iron bars), 2 days each."""
        ORE = {"Copper Bar": ("Copper Ore", 75 if self.year == 1 else 150), "Iron Bar": ("Iron Ore", 150 if self.year == 1 else 250)}
        def ensure(bar):   # buy ore at Clint (Y1 prices) and smelt; coal from stock or 150g
            need = max(0, 5 - self.inv.get(bar, 0))
            ore, price = ORE[bar]
            cost = need * (5 * price + (0 if self.inv.get("Coal", 0) >= need else 150))
            if need and self.gold - cost >= self.res():
                self.gold -= cost; self.add(bar, need)
                self.inv["Coal"] = max(0, self.inv.get("Coal", 0) - need)
        if self.steel_axe is None and getattr(self, "copper_axe", None) is None: ensure("Copper Bar")
        if getattr(self, "copper_axe", None) is not None and self.steel_axe is None: ensure("Iron Bar")
        if self.steel_axe is None and getattr(self, "copper_axe", None) is None and self.inv.get("Copper Bar", 0) >= 5 and self.gold >= 2000 + self.res():
            self.gold -= 2000; self.inv["Copper Bar"] -= 5; self.copper_axe = self.t + 2
        elif getattr(self, "copper_axe", None) is not None and self.copper_axe <= self.t and self.steel_axe is None and self.inv.get("Iron Bar", 0) >= 5 and self.gold >= 5000 + self.res():
            self.gold -= 5000; self.inv["Iron Bar"] -= 5; self.steel_axe = self.t + 2
            self.log.append((self.t, "steel axe", ""))
        return 10

    def want_shop(self):
        """Would a shop trip buy something today? (mirrors purchases() rules, cheaply)"""
        nd = self.needed(); g0 = self.gold - self.res()
        wp, spc = (10, 20) if self.year == 1 else (50, 100)
        if any(nd.get(it, 0) > self.inv.get(it, 0) for it in ("Wood", "Stone")) and g0 > 99 * spc: return "robin"
        if self.sprinkled < self.p.sprinkler_goal and self.level("farming") >= 2 and g0 > 1425: return "pierre"
        if self.p.vault_first and not self.room_done("Vault"):
            nxt = next((b for b in ("2,500g", "5,000g", "10,000g", "25,000g") if b not in self.done), None)
            if nxt and self.gold < int(nxt.replace(",", "").replace("g", "")) + self.res(): return None
        COST = {"Coop": 4000 + 300 * wp + 100 * spc, "Big Coop": 10000 + 400 * wp + 150 * spc, "Deluxe Coop": 20000 + 500 * wp + 200 * spc,
                "Barn": 6000 + 350 * wp + 150 * spc, "Big Barn": 12000 + 450 * wp + 200 * spc, "Deluxe Barn": 25000 + 550 * wp + 300 * spc,
                "Apple Sapling": 4000, "Pomegranate Sapling": 6000, "House": 10000 + 450 * wp}
        order = list(self.p.build_order) + (["Big Barn", "Deluxe Barn"] if self.p.pig else []) + (["House"] if self.p.kitchen else [])
        nxt = next((b for b in order if b not in self.buildings), None)
        if nxt and g0 >= COST[nxt] + 2000: return "robin" if not nxt.endswith("Sapling") else "pierre"
        if self.level("fishing") >= 3 and self.pots < self.p.crab_pots and g0 >= 1500: return "willy"
        return None

    def want_clint(self):
        g0 = self.gold - self.res()
        if self.steel_axe is not None: return False
        ca = getattr(self, "copper_axe", None)
        if ca is None: return g0 >= 2000 + max(0, 5 - self.inv.get("Copper Bar", 0)) * 525
        return ca <= self.t and g0 >= 5000 + max(0, 5 - self.inv.get("Iron Bar", 0)) * 900

    def do_hardwood(self, dur):
        self.add("Hardwood", 6); self.xp["foraging"] += 30; return dur

    def do_forage(self, loc):
        def run(w, dur):
            items = w.forage.get(loc, [])
            for i in items: w.add(i); w.xp["foraging"] += 7
            w.forage[loc] = []
            return dur
        return run

    def do_fish(self, fish, p):
        def run(w, dur):
            casts = int(dur // w.s.cast_min)
            got = 0
            for _ in range(casts):
                if w.r.random() < p * (1 - w.s.escape):
                    got += 1; break
            used = (_ + 1) * w.s.cast_min if casts else 0
            if got: w.add(fish); w.xp["fishing"] += 15
            w.xp["fishing"] += 3 * max(0, (_ if casts else 0))
            # other casts still catch sellable fish
            w.sell("fish", int(max(0, (_ if casts else 0)) * (1 - w.s.escape)), w.s.fish_value * (1.25 if "Fisher" in w.prof else 1))
            return used
        return run

    def do_money_fish(self, w, dur):
        casts = int(dur // w.s.cast_min)
        w.sell("fish", int(casts * (1 - w.s.escape)), w.s.fish_value * (1.25 if "Fisher" in w.prof else 1))
        w.xp["fishing"] += casts * 8
        return casts * w.s.cast_min

    def do_mine(self, w, dur):
        floors = dur / 60 * w.s.floors_per_hour
        w.mine(floors, w.needed())
        w.xp["mining"] += int(floors * 10)   # mine() adds 30/floor; total ~40/floor
        return dur

    def do_desert(self, w, dur):
        w.gold -= 500
        for it in ("Coconut", "Cactus Fruit"):
            if it in w.needed() and w.gold >= 200: w.gold -= 200; w.add(it)
        sl = next((s for s in w.fishtab.get("Sandfish", []) if s["loc"] == "Desert"), None)
        if "Sandfish" in w.needed() and sl:
            casts = int(120 // w.s.cast_min)
            if any(w.r.random() < sl["p"] * (1 - w.s.escape) for _ in range(casts)): w.add("Sandfish")
        return dur

    # ---------- day bookkeeping
    def plant_today(self):
        # reuse v0 planting rules but without its watering/growth step
        nd = self.needed()
        active = {}
        for pl in self.plantings:
            if not pl["dead"]: active[pl["crop"]] = active.get(pl["crop"], 0) + pl["n"]
        for crop, n in self.p.crops.get(self.season, {}).items():
            if (crop in nd or crop + "*" in nd) and active.get(crop, 0) == 0 and self.planted_once.get((self.t // 28, crop)) is None:
                if self.plant(crop, n): self.planted_once[(self.t // 28, crop)] = True
        mc = self.p.money_crop.get(self.season)
        if mc and self.dow() != 2:
            tiles = sum(active.values())
            room = self.p.max_tiles + self.sprinkled - tiles
            spare = self.gold - self.res() - self.seed_budget()
            e_left = 270 - 2 * self.dry_tiles() - self.target_energy_reserve
            room = min(room, int(e_left / 2))
            if room > 0 and spare > 0:
                seed = next(sid for sid, c in g.crops().items() if c["crop"] == mc)
                price = g.crops()[seed]["pierre"] + (100 if self.p.fert_money and self.t >= 14 else 0)
                n = int(min(room, spare // price))
                if n >= 5: self.plant(mc, n, money=True)

    def seed_budget(self):
        """Gold to keep for bundle-crop seeds of this and next season (last 8 days of a season)."""
        nd = self.needed(); cost = 0
        seasons = [self.season] + ([W.SE[(self.t // 28 + 1) % 4]] if self.dom >= 20 else [])
        for se in seasons:
            for crop, n in self.p.crops.get(se, {}).items():
                if crop in nd or crop + "*" in nd:
                    if se == self.season and self.planted_once.get((self.t // 28, crop)): continue
                    seed = next((sid for sid, c in g.crops().items() if c["crop"] == crop), None)
                    pr = g.crops()[seed]["pierre"] if seed else None
                    if pr: cost += (pr + (100 if self.p.fert else 0)) * n
        return cost

    def dry_tiles(self):
        tiles = sum(pl["n"] for pl in self.plantings if not pl["dead"])
        return max(0, tiles - self.sprinkled)

    def end_of_day(self):
        # kitchen: cook a Fried Egg from an Egg (house upgrade built)
        if self.buildings.get("House", 10**6) <= self.t and "Fried Egg" in self.needed() and self.inv.get("Egg", 0) >= 1:
            self.inv["Egg"] -= 1; self.add("Fried Egg")
        rain = self.w == "rain"
        watered = rain or self.watered_today or self.dry_tiles() == 0 or self.season == "winter"
        for pl in self.plantings:
            if pl["dead"]: continue
            if self.season not in pl["seasons"]: pl["dead"] = True; continue
            if watered: pl["grown"] += 1
            if pl["grown"] >= pl["next"]:
                self.harvest(pl)
                if "Tiller" in self.prof: self.sell("tiller bonus", 1, int(pl["n"] * pl["items"] * pl["sell"] * 0.1))
        self.plant_debt = 0
        # forage for tomorrow (GameLocation.DayUpdate:5123, seasonUpdate): every 7th day wipe + 3 spawns;
        # day 1 (new season, also wiped by seasonUpdate) 2 spawns; first 4 days of the game +1
        tom = self.dom % 28 + 1
        n = 1
        if tom % 7 == 0: self.forage = {}; n = 3
        if tom == 1: self.forage = {}; n = 2
        if self.t + 1 < 4: n += 1
        for k in range(n): self.spawn_forage(extras=(k == 0))
        if self.p.cave == "bats" and self.earned >= 25000 and not self.bats: self.bats = True; self.log.append((self.t, "bats", ""))
        for sk, pr in (("farming", "Tiller"), ("fishing", "Fisher"), ("mining", "Miner")):
            if self.level(sk) >= 5: self.prof.add(pr)
        if self.room_done("Vault") and "bus" not in self.buildings: self.buildings["bus"] = self.t + 1
        # donations happen only via the cc task; check completion
        if len(self.done) >= len(self.slots): self.finished = self.t

    def run(self, cap_days=336):
        self.finished = None
        while self.t < cap_days:
            self.day()
            if self.finished is not None: return self.finished
            self.t += 1
        return None
