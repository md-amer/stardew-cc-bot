"""Day-level Stardew world simulator for Community Center planning.

One call = one Monte Carlo run of a strategy (Plan) from Spring 1 Year 1 to CC completion (or a cap).
Game rules come from NUMBERS.md (data/code) and the compute/ results. Bot speeds come from our run
(empirical.py) and can be swapped for 'human' speeds to see what execution speed is worth.

MODEL ASSUMPTIONS (each is a knob in Speeds or Plan; change and re-run):
- Day = 1200 game minutes (6:00-2:00) minus fixed overhead (menus, waiting, walking between steps).
- Watering costs speed.water_min per unsprinkled tile, 2 energy per tile (basic can). Rain waters all.
- Planting/clearing costs speed.plant_min per tile. Harvest costs speed.harvest_min per tile.
- Fishing: speed.cast_min game minutes per cast, 8 energy per cast, escape rate speed.escape.
  Catch chances from fishsim (precomputed per spot/season/hour/weather).
- Mining: speed.floors_per_hour; per floor fixed expected yields (MINE_YIELD) by area; energy per floor.
  Elevator every 5 floors keeps progress.
- Animals: petted daily if plan says so (speed.animal_min each). Deluxe rolls exact (FarmAnimal.cs).
- Forage: each in-season location adds U{1..4} items/day (cap 6); a visit collects all (forage tour cost).
- Cart Fri/Sun: each needed item 10/334 chance; bought if gold allows.
- Fruit bats after 25,000g earned (FarmCave.cs rule), if plan.cave == 'bats'.
- Shops: closed days per wiki (Pierre Wed, Robin Tue, Marnie Mon/Tue, festivals). Purchases happen in
  the morning trip if open.
- Gold-quality rolls exact formula (Crop.cs:565). Crop sale at base price (gold x1.5).
- Not modelled: Skull Cavern, Secret Notes, friendship gifts, special orders, tool upgrade downtime
  (except steel axe for Secret Woods), stardrops/energy food, combat deaths.
"""
import random, math, json, os
from dataclasses import dataclass, field
import gamedata as g

HERE = os.path.dirname(os.path.abspath(__file__))
SE = ["spring", "summer", "fall", "winter"]
FESTIVAL = {(0, 12), (0, 23), (1, 10), (2, 15), (3, 7), (3, 24)}   # day festivals (season, dom-1): shops closed
OBJ = lambda n: g.obj(g.id_by_name()[n])
_PX = {"Large Egg (brown)": 95, "fish": 60}
PRICE = lambda n: _PX[n] if n in _PX else OBJ(n)["Price"]


@dataclass
class Speeds:
    overhead: float = 283        # game minutes/day lost (our run's 'other')
    water_min: float = 2.57      # per unsprinkled tile (our run)
    plant_min: float = 1.5
    harvest_min: float = 0.8
    cast_min: float = 20         # per cast incl. walking/reeling (our run median)
    escape: float = 0.10
    floors_per_hour: float = 0.84
    animal_min: float = 3
    forage_tour_min: float = 90  # per location visit incl. travel
    shop_trip_min: float = 40
    cart_trip_min: float = 50
    desert_trip_min: float = 420
    fish_value: float = 20       # realised g per money-fishing cast (our run ~17)

BOT = Speeds()
HUMAN = Speeds(overhead=120, water_min=0.35, plant_min=0.4, harvest_min=0.3, cast_min=6, escape=0.05,
               floors_per_hour=6, animal_min=1, forage_tour_min=45, shop_trip_min=25, cart_trip_min=30, desert_trip_min=300, fish_value=45)


@dataclass
class Plan:
    """Strategy knobs the optimizer searches over."""
    crops: dict = field(default_factory=lambda: {   # season -> {crop: tiles}
        "spring": {"Parsnip": 2, "Green Bean": 2, "Cauliflower": 2, "Potato": 2},
        "summer": {"Melon": 30, "Tomato": 2, "Hot Pepper": 2, "Blueberry": 2, "Corn": 12, "Sunflower": 2, "Poppy": 2, "Wheat": 12},
        "fall": {"Pumpkin": 30, "Eggplant": 2, "Yam": 2, "Corn": 2, "Sunflower": 2}})
    fert: int = 1                     # fertilizer level on bundle crops (0 none, 1 basic)
    sprinkler_goal: int = 60          # tiles to cover with basic sprinklers (bought ore, 4 tiles each)
    build_order: list = field(default_factory=lambda: ["Coop", "Barn", "Big Coop", "Deluxe Coop", "Apple Sapling", "Pomegranate Sapling"])
    reserve: int = 500                # gold kept for seeds
    vault_first: bool = True          # pay Vault before buildings when both affordable
    mine_days_per_week: int = 2       # days spent mining until floor goal
    mine_goal: int = 80
    cave: str = "bats"
    pig: bool = False
    kitchen: bool = False
    chickens: int = 4
    fish_money_hours: float = 0.0
    crab_pots: int = 3
    money_crop: dict = field(default_factory=lambda: {"spring": "Potato", "summer": "Blueberry", "fall": "Pumpkin"})
    max_tiles: int = 80               # hand-watered tiles cap (sprinkled tiles come on top)
    fert_money: bool = False     # extra daily fishing for money once bundle fish are done


# expected yields per mined floor (ASSUMPTION; calibrate against logs)
MINE_YIELD = {0: {"Copper Ore": 4, "Coal": 0.4, "Stone": 15, "Geode": 0.5, "Quartz": 0.3, "Earth Crystal": 0.1, "Slime": 0.8, "Cave Carrot": 0.1, "Amethyst": 0.05},
              40: {"Iron Ore": 4, "Copper Ore": 1, "Coal": 0.5, "Stone": 15, "Frozen Geode": 0.5, "Quartz": 0.3, "Frozen Tear": 0.1, "Bat Wing": 0.6, "Solar Essence": 0.3, "Aquamarine": 0.04},
              80: {"Gold Ore": 3, "Iron Ore": 1, "Coal": 0.6, "Stone": 15, "Magma Geode": 0.5, "Quartz": 0.3, "Fire Quartz": 0.1, "Void Essence": 0.4, "Purple Mushroom": 0.05, "Red Mushroom": 0.05}}


class World:
    def __init__(self, plan, speeds=BOT, seed=0, fishtab=None):
        self.p, self.s = plan, speeds
        self.r = random.Random(seed)
        self.t = 0
        self.gold = 500; self.earned = 0
        self.inv = {}
        self.xp = {"farming": 0, "fishing": 0, "foraging": 0, "mining": 0}
        self.floor = 0
        self.buildings = {}          # name -> ready day
        self.animals = []            # dicts
        self.plantings = []          # dicts
        self.sprinkled = 0
        self.bats = False
        self.trees = {}              # fruit -> mature day
        self.done = {}               # bundle -> day
        self.slots = self._init_slots()
        self.log = []
        self.fishtab = fishtab or json.load(open(os.path.join(HERE, "data", "fish_slots.json")))
        self.forage = {}             # location -> list of items on map
        self.steel_axe = None
        self.pots = 0
        self.src = {}
        self.planted_once = {}
        self.tappers = []

    # ---------------- calendar
    @property
    def season(self): return SE[(self.t // 28) % 4]
    @property
    def dom(self): return self.t % 28 + 1
    @property
    def year(self): return self.t // 112 + 1
    def dow(self): return (self.dom - 1) % 7   # 0 Mon .. 6 Sun
    def festival(self): return ((self.t // 28) % 4, self.t % 28) in FESTIVAL

    def weather(self):
        s, d = self.season, self.dom
        if self.year == 1 and s == "spring" and d in (1, 2, 3, 5): return "sun"
        if self.year == 1 and s == "spring" and d == 4: return "rain"
        if s == "summer":
            if d > 1 and self.r.random() < 0.12 + 0.003 * d: return "rain"
            return "sun"
        if s in ("spring", "fall"): return "rain" if self.r.random() < 0.183 else "sun"
        return "snow" if self.r.random() < 0.63 else "sun"

    # ---------------- bundles
    def _init_slots(self):
        out = {}
        for b in g.bundles():
            if b["room"] == "Abandoned Joja Mart": continue
            its = [("Large Egg (brown)" if i["id"] == "182" else i["name"], i["qty"], i["quality"]) for i in b["items"]]
            out[b["name"]] = {"need": b["need"], "items": its, "got": set(), "room": b["room"]}
        return out

    def needed(self):
        """Item names still useful for some bundle (quality ignored except gold crops)."""
        n = {}
        for b, v in self.slots.items():
            if b in self.done: continue
            for k, (nm, q, ql) in enumerate(v["items"]):
                if k in v["got"]: continue
                key = nm + ("*" if ql == 2 else "")
                n[key] = n.get(key, 0) + q
        return n

    def donate(self):
        for b, v in self.slots.items():
            if b in self.done: continue
            for k, (nm, q, ql) in enumerate(v["items"]):
                if k in v["got"] or len(v["got"]) >= v["need"]: continue
                if nm == "gold":
                    continue
                key = nm + ("*" if ql == 2 else "")
                if self.inv.get(key, 0) >= q:
                    self.inv[key] -= q; v["got"].add(k); self.log.append((self.t, "item", key))
            if len(v["got"]) >= v["need"]:
                self.done[b] = self.t; self.log.append((self.t, "bundle", b))
                self.reward(b)

    def pay_vault(self):
        for b in ("2,500g", "5,000g", "10,000g", "25,000g"):
            if b in self.done: continue
            amt = int(b.replace(",", "").replace("g", ""))
            if self.gold - amt >= self.res():
                self.gold -= amt; self.done[b] = self.t; self.log.append((self.t, "bundle", b))
            return

    def res(self):
        return self.p.reserve + getattr(self, "extra_reserve", 0)

    def room_done(self, room):
        return all(b in self.done for b, v in self.slots.items() if v["room"] == room)

    def reward(self, b):
        if b == "Fall Crops": self.inv["Bee House"] = self.inv.get("Bee House", 0) + 1
        if b == "Quality Crops": self.inv["Preserves Jar"] = self.inv.get("Preserves Jar", 0) + 1
        if b == "Animal": self.inv["Cheese Press"] = 1
        if b == "Artisan": self.inv["Keg"] = 1
        if b == "Field Research": self.inv["Recycling Machine"] = 1

    def level(self, sk):
        xp = self.xp[sk]
        return sum(1 for x in [100, 380, 770, 1300, 2150, 3300, 4800, 6900, 10000, 15000] if xp >= x)

    def add(self, item, n=1):
        if n: self.inv[item] = self.inv.get(item, 0) + n

    def sell(self, item, n, price):
        self.gold += n * price; self.earned += n * price
        self.src[item] = self.src.get(item, 0) + n * price

    # ---------------- day
    def run(self, cap_days=336):
        while self.t < cap_days:
            self.day()
            if len(self.done) >= len(self.slots): return self.t
            self.t += 1
        return None

    def day(self):
        s, sp = self.season, self.s
        w = self.weather(); self.w = w
        self.luck = self.r.randint(-100, 100) / 1000
        mins = 1200 - sp.overhead
        energy = 270
        shops = not self.festival()
        # overnight: trees, buildings, animals, machines
        self.overnight()
        # crops: water + harvest
        mins, energy = self.crop_day(mins, energy, w)
        # animals
        for a in self.animals:
            mins -= sp.animal_min
        # morning shop trip: buy / build / vault
        if shops:
            mins -= sp.shop_trip_min
            self.purchases()
        # cart
        if self.dow() in (4, 6):
            mins -= sp.cart_trip_min; self.cart()
        # Gus: Maki Roll + dish of the day (Fried Egg)
        nd = self.needed()
        if shops and ("Maki Roll" in nd or "Fried Egg" in nd):
            mins -= sp.shop_trip_min
            if "Maki Roll" in nd and self.gold >= 300 + self.res(): self.gold -= 300; self.add("Maki Roll")
            if "Fried Egg" in nd and self.r.random() < 1 / 41 and self.gold >= 400: self.gold -= 400; self.add("Fried Egg")
        # bundle fish / forage / mining by priority
        mins, energy = self.targets(mins, energy)
        if "Hardwood" in nd and self.steel_axe is not None and self.steel_axe <= self.t: self.add("Hardwood", 6)
        self.donate()
        self.pay_vault()
        if self.room_done("Vault") and "bus" not in self.buildings: self.buildings["bus"] = self.t + 1
        if self.p.cave == "bats" and self.earned >= 25000 and not self.bats: self.bats = True; self.log.append((self.t, "bats", ""))

    # ---------------- subsystems
    def overnight(self):
        if self.bats:
            while self.r.random() < 0.66:
                k = self.r.randrange(5)
                it = ["Salmonberry", "Spice Berry", "Wild Plum", "Blackberry"][k] if k < 4 else ("Apple" if self.r.random() < 0.1 else self.r.choice(["Apricot", "Orange", "Peach", "Pomegranate", "Cherry"]))
                self.add(it)
        for fr, day in self.trees.items():
            fs = {"Apple": "fall", "Pomegranate": "fall", "Apricot": "spring", "Cherry": "spring", "Orange": "summer", "Peach": "summer"}[fr]
            if self.t >= day and self.season == fs: self.add(fr)
        if self.pots:
            dist = TAB["crab_pot"]["ocean/none"]
            items, ps = zip(*dist.items())
            for _ in range(self.pots):
                it = self.r.choices(items, ps)[0]
                if it != "junk":
                    self.add(it)
                    if self.inv[it] > 1: self.inv[it] -= 1; self.sell(it, 1, PRICE(it))
            self.gold -= 0
        for tp in self.tappers:
            if self.t >= tp[1]:
                self.add(tp[0]); tp[1] = self.t + {"Oak Resin": 7, "Maple Syrup": 9, "Pine Tar": 5}[tp[0]]
        # machines for artisan bundle items (one each, enough for bundles)
        nd = self.needed()
        if self.inv.get("Bee House") and self.season != "winter" and self.t % 4 == 0: self.add("Honey")
        if self.inv.get("Preserves Jar") and "Jelly" in nd:
            fruit = next((f for f in ("Salmonberry", "Spice Berry", "Blackberry", "Wild Plum", "Apple", "Apricot", "Cherry") if self.inv.get(f, 0) > (1 if f in nd else 0)), None)
            if fruit: self.inv[fruit] -= 1; self.add("Jelly")
        if self.inv.get("Keg") and "Wine" in nd and getattr(self, "wine_day", None) is None:
            fruit = next((f for f in ("Salmonberry", "Spice Berry", "Blackberry", "Apple", "Apricot", "Cherry", "Orange", "Peach") if self.inv.get(f, 0) > (1 if f in nd else 0)), None)
            if fruit: self.inv[fruit] -= 1; self.wine_day = self.t + 7
        if getattr(self, "wine_day", None) == self.t: self.add("Wine"); self.wine_day = None
        if self.inv.get("Cheese Press") and self.inv.get("Milk", 0) and "Cheese" in nd: self.inv["Milk"] -= 1; self.add("Cheese")
        if self.level("farming") >= 6 and "Cheese Press" not in self.inv: self.inv["Cheese Press"] = 1
        if self.level("farming") >= 3 and "Bee House" not in self.inv and self.gold > 2000: self.inv["Bee House"] = 1; self.gold -= 600
        if self.level("farming") >= 4 and "Preserves Jar" not in self.inv: self.inv["Preserves Jar"] = 1; self.gold -= 300
        if self.level("farming") >= 8 and "Keg" not in self.inv: self.inv["Keg"] = 1; self.gold -= 800
        # animals
        for a in self.animals:
            if self.t < a["ready"]: continue
            a["f"] = min(1000, a["f"] + 15)
            a["since"] += 1
            if self.t < a["adult"]: continue
            if self.season == "winter" and a["kind"] == "Pig": continue
            if a["since"] >= a["dtp"]:
                hap = 255
                deluxe = self.r.random() < hap / 150 and a["f"] >= a["minf"] and self.r.random() < (a["f"] + hap * 1.5) / a["div"] + self.luck * a["lm"]
                a["since"] = 0
                item = a["deluxe"] if deluxe else a["prod"]
                self.add(item)
                if not deluxe and item == "Milk": pass
                # sell surplus not needed
                keep = ("Milk", "Wool") + (("Egg",) if self.p.kitchen and "Fried Egg" in self.needed() else ())
                if item not in self.needed() and item not in keep or self.inv.get(item, 0) > 3:
                    self.inv[item] -= 1; self.sell(item, 1, PRICE(item))

    def crop_day(self, mins, energy, w):
        sp = self.s
        # plant new season plan on first possible day
        # bundle crops: plant once per season while still needed
        nd = self.needed()
        active = {}
        for pl in self.plantings:
            if not pl["dead"]: active[pl["crop"]] = active.get(pl["crop"], 0) + pl["n"]
        for crop, n in self.p.crops.get(self.season, {}).items():
            if (crop in nd or crop + "*" in nd or crop == "Wheat" and "Wheat" in nd) and active.get(crop, 0) == 0 and self.planted_once.get((self.t // 28, crop)) is None:
                if self.plant(crop, n): self.planted_once[(self.t // 28, crop)] = True
        # money crop: reinvest spare gold daily up to the tile cap
        mc = self.p.money_crop.get(self.season)
        if mc:
            tiles = sum(active.values())
            room = self.p.max_tiles + self.sprinkled - tiles
            spare = self.gold - self.res()
            if room > 0 and spare > 0:
                seed = next(sid for sid, c in g.crops().items() if c["crop"] == mc)
                price = g.crops()[seed]["pierre"] + (100 if self.p.fert_money and self.t >= 14 else 0)
                n = int(min(room, spare // price))
                if n >= 5 and self.dow() != 2: self.plant(mc, n, money=True)
        mins -= getattr(self, "plant_debt", 0); self.plant_debt = 0
        rain = w in ("rain",)
        tiles = sum(pl["n"] for pl in self.plantings if not pl["dead"])
        dry = max(0, tiles - self.sprinkled)
        if self.season != "winter" and not rain and dry:
            cost = dry * sp.water_min
            e = dry * 2
            if cost <= mins and e <= energy:
                mins -= cost; energy -= e; watered = True
            else:
                watered = False
        else:
            watered = True
        for pl in self.plantings:
            if pl["dead"]: continue
            if self.season not in pl["seasons"]: pl["dead"] = True; continue
            if watered: pl["grown"] += 1
            if pl["grown"] >= pl["next"]:
                mins -= pl["n"] * sp.harvest_min
                self.harvest(pl)
        return mins, energy

    def plant(self, crop, n, money=False):
        if not n: return
        seed = next((sid for sid, c in g.crops().items() if c["crop"] == crop), None)
        c = g.crops()[seed]
        price = c["pierre"]
        if price is None or (crop == "Red Cabbage" and self.year < 2): return
        if self.season not in c["seasons"]: return
        days_left = 28 - self.dom + 28 * (len(c["seasons"]) - 1 - c["seasons"].index(self.season))
        if c["grow_days"] > days_left: return
        use_f = (self.p.fert_money if money else self.p.fert) and self.t >= 14
        cost = (price + (100 if use_f else 0)) * n
        while n and cost > self.gold:
            n -= 1; cost = (price + (100 if use_f else 0)) * n
        if n <= 0: return False
        self.gold -= cost
        mins_cost = n * self.s.plant_min
        self.plant_debt = getattr(self, "plant_debt", 0) + mins_cost
        fert = 1 if use_f else 0
        self.plantings.append({"crop": crop, "n": n, "grown": 0, "next": c["grow_days"], "regrow": c["regrow"],
                               "seasons": c["seasons"], "dead": False, "fert": fert,
                               "items": (c["min_stack"] + c["max_stack"]) / 2, "extra": c["extra_chance"], "sell": c["sell"]})
        return True

    def harvest(self, pl):
        L = self.level("farming")
        p = 0.2 * L / 10 + 0.2 * pl["fert"] * (L + 2) / 12 + 0.01
        n = pl["n"]
        gold = sum(1 for _ in range(n) if self.r.random() < p)
        items = n * pl["items"] + (n * pl["extra"] / (1 - min(.9, pl["extra"])) if pl["extra"] else 0)
        items = int(round(items))
        crop = pl["crop"]
        nd = self.needed()
        keep_gold = min(gold, max(0, nd.get(crop + "*", 0) - self.inv.get(crop + "*", 0)))
        self.add(crop + "*", keep_gold)
        keep = min(items - keep_gold, max(0, nd.get(crop, 0) - self.inv.get(crop, 0)) + (5 if crop in ("Wheat",) else 0))
        if crop == "Wheat": keep = min(items, max(0, 10 - self.inv.get("Wheat", 0)))
        self.add(crop, keep)
        self.sell(crop, items - keep - keep_gold, pl["sell"])
        self.xp["farming"] += n * round(16 * math.log(0.018 * pl["sell"] + 1))
        if pl["regrow"] > 0: pl["next"] = pl["grown"] + pl["regrow"]
        else: pl["dead"] = True

    def purchases(self):
        nd = self.needed()
        wp, spc = (10, 20) if self.year == 1 else (50, 100)
        robin = self.dow() != 1
        # Construction bundle materials (Robin)
        if robin:
            for it, pr in (("Wood", wp), ("Stone", spc)):
                want = nd.get(it, 0) - self.inv.get(it, 0)
                if want > 0 and self.gold - want * pr >= self.res():
                    self.gold -= want * pr; self.add(it, want)
            # tide-pool bridge (300 wood) when Sea Urchin needed
            if "Sea Urchin" in nd and not self.buildings.get("bridge") is not None and "bridge" not in self.buildings and self.gold - 300 * wp >= self.res():
                self.gold -= 300 * wp; self.buildings["bridge"] = self.t
        # Silo (needs copper bars) then Hay from Marnie (Mon/Tue closed)
        if "Hay" in nd and "Silo" not in self.buildings and self.inv.get("Copper Bar", 0) >= 6 and robin and self.gold >= 100 + 100 * spc + self.res():
            self.gold -= 100 + 100 * spc; self.inv["Copper Bar"] -= 5; self.buildings["Silo"] = self.t + 2
        if "Hay" in nd and self.buildings.get("Silo", 10**6) <= self.t and self.dow() not in (0, 1) and self.gold >= 500 + self.res():
            self.gold -= 500; self.add("Hay", 10)
        # crab pots after Fishing 3 (Willy, closed sunny Saturdays)
        if self.level("fishing") >= 3 and self.pots < self.p.crab_pots and self.dow() != 5 and self.gold >= 1500 + self.res():
            self.gold -= 1500; self.pots += 1
        # tappers after Foraging 4 (40 wood + 2 copper bars): one each of oak, maple, pine
        if self.level("foraging") >= 4 and len(self.tappers) < 3 and self.inv.get("Copper Bar", 0) < 2 and self.gold - 2 * 525 >= self.res():
            self.gold -= 2 * 525; self.add("Copper Bar", 2)   # buy 10 copper ore at Clint (Y1 75g) + 2 coal and smelt
        if self.level("foraging") >= 4 and len(self.tappers) < 3 and self.inv.get("Copper Bar", 0) >= 2:
            kind = ["Oak Resin", "Maple Syrup", "Pine Tar"][len(self.tappers)]
            self.inv["Copper Bar"] -= 2; self.tappers.append([kind, self.t + {"Oak Resin": 7, "Maple Syrup": 9, "Pine Tar": 5}[kind]])
        # sprinklers: basic = copper bar + iron bar, bars bought as ore (Y1 Clint) + coal
        while self.sprinkled < self.p.sprinkler_goal and self.level("farming") >= 2 and self.dow() != 4:
            cost = 5 * 75 + 5 * 150 + 2 * 150
            if self.gold - cost < self.res(): break
            self.gold -= cost; self.sprinkled += 4
        if self.p.vault_first and not self.room_done("Vault"):
            nxt = next((b for b in ("2,500g", "5,000g", "10,000g", "25,000g") if b not in self.done), None)
            if nxt and self.gold < int(nxt.replace(",", "").replace("g", "")) + self.res():
                return  # save up
        COST = {"Coop": (4000, 300, 100), "Big Coop": (10000, 400, 150), "Deluxe Coop": (20000, 500, 200),
                "Barn": (6000, 350, 150), "Big Barn": (12000, 450, 200), "Deluxe Barn": (25000, 550, 300),
                "Apple Sapling": (4000, 0, 0), "Pomegranate Sapling": (6000, 0, 0), "House": (10000, 450, 0)}
        order = list(self.p.build_order)
        if self.p.pig: order += ["Big Barn", "Deluxe Barn"]
        if self.p.kitchen: order += ["House"]
        for b in order:
            if b in self.buildings: continue
            if b.endswith("Sapling") and self.season == "winter": continue
            gcost, wood, stone = COST[b]
            wp, spc = (10, 20) if self.year == 1 else (50, 100)
            total = gcost + wood * wp + stone * spc
            prev = {"Big Coop": "Coop", "Deluxe Coop": "Big Coop", "Big Barn": "Barn", "Deluxe Barn": "Big Barn"}.get(b)
            if prev and (prev not in self.buildings or self.buildings[prev] > self.t): return
            if self.gold - total < self.res(): return
            if b in ("Coop", "Barn", "Big Coop", "Deluxe Coop", "Big Barn", "Deluxe Barn", "House") and self.dow() == 1: return  # Robin Tue
            self.gold -= total
            ready = self.t + (3 if b in ("Coop", "Barn", "House") else 2)
            self.buildings[b] = ready
            if b.endswith("Sapling"): self.trees[b.split()[0]] = self.t + 28
            self.log.append((self.t, "build", b))
            self.buy_animals(b, ready)
            return

    def buy_animals(self, b, ready):
        A = g.raw("FarmAnimals")
        def mk(kind, prod, deluxe, price):
            a = A[kind]
            self.animals.append({"kind": kind, "ready": ready, "adult": ready + (a.get("DaysToMature") or 0), "f": 0, "since": 0,
                                 "dtp": a.get("DaysToProduce", 1), "div": a.get("DeluxeProduceCareDivisor", 1200.0),
                                 "minf": a.get("DeluxeProduceMinimumFriendship", 200) if "DeluxeProduceMinimumFriendship" in a else 0,
                                 "lm": a.get("DeluxeProduceLuckMultiplier", 0.0), "prod": prod, "deluxe": deluxe})
            self.gold -= price
        if b == "Coop":
            for _ in range(self.p.chickens):
                col = self.r.choice(["White Chicken", "Brown Chicken"])
                mk(col, "Egg", "Large Egg" if col == "White Chicken" else "Large Egg (brown)", 400)
        if b == "Big Coop": mk("Duck", "Duck Egg", "Duck Feather", 600)
        if b == "Deluxe Coop": mk("Rabbit", "Wool", "Rabbit's Foot", 4000)
        if b == "Barn": mk("White Cow", "Milk", "Large Milk", 750 + 1000)
        if b == "Deluxe Barn": mk("Pig", "Truffle", "Truffle", 8000)

    def cart(self):
        nd = self.needed()
        for item in list(nd):
            nm = item.rstrip("*")
            if item.endswith("*") or nm in ("gold", "Wood", "Stone", "Hay", "Quartz", "Earth Crystal", "Frozen Tear", "Fire Quartz", "Aquamarine", "Frozen Geode"): continue
            if self.r.random() < 10 / 334:
                base = PRICE(nm) if nm in g.id_by_name() else 100
                price = max(self.r.randrange(1, 11) * 100, base * self.r.choice([3, 4, 5]))
                if self.gold - price >= self.res():
                    self.gold -= price; self.add(nm); self.log.append((self.t, "cart", nm))
            if nm == "Red Cabbage" and self.season == "summer" and self.r.random() < 10 / 334 and self.gold >= 300:
                self.gold -= 300; self.plantings.append({"crop": "Red Cabbage", "n": 1, "grown": 0, "next": 9, "regrow": -1, "seasons": ["summer"], "dead": False, "fert": 0, "items": 1, "extra": 0, "sell": 260})

    def targets(self, mins, energy):
        """Spend the rest of the day: bundle fish in window, forage, mining, money fishing."""
        sp = self.s; nd = self.needed()
        # forage tour: in-season forage locations, only if a needed forage item spawns there
        self.spawn_forage()
        for loc, items in self.forage.items():
            want = [i for i in items if i in nd]
            if want and mins > sp.forage_tour_min and self.access(loc):
                mins -= sp.forage_tour_min
                for i in items: self.add(i); self.xp["foraging"] += 7
                self.forage[loc] = []
        # bundle fish whose window is open today: pick best slot
        best = None
        for fish, slots in self.fishtab.items():
            if fish not in nd: continue
            for sl in slots:
                if sl["season"] != self.season or (sl["weather"] == "rain") != (self.w == "rain"): continue
                if not self.access(sl["loc"]): continue
                if best is None or sl["p"] > best[1]["p"]: best = (fish, sl)
        while best and mins >= sp.cast_min * 3 and energy >= 24:
            fish, sl = best
            casts = int(min(mins / sp.cast_min, energy / 8, 12))
            mins -= casts * sp.cast_min; energy -= casts * 8
            got = sum(1 for _ in range(casts) if self.r.random() < sl["p"] * (1 - sp.escape))
            self.xp["fishing"] += casts * 8
            if got: self.add(fish, got)
            if self.desert_trip(sl["loc"]): mins -= 0
            break
        # mining
        if self.floor < self.p.mine_goal or any(i in nd for i in ("Quartz", "Earth Crystal", "Frozen Tear", "Fire Quartz", "Slime", "Bat Wing", "Solar Essence", "Void Essence", "Frozen Geode", "Aquamarine", "Copper Bar", "Iron Bar", "Gold Bar")):
            if self.dow() < self.p.mine_days_per_week and self.t >= 4 and mins > 120:
                hours = mins / 60
                floors = hours * sp.floors_per_hour
                floors = min(floors, energy / 20)   # ~20 energy per floor (pickaxe swings)
                self.mine(floors, nd)
                mins = 0; energy = 0
        # money fishing with leftover
        if mins > 60 and self.season != "winter" or (mins > 60 and self.p.fish_money_hours):
            casts = int(min(mins / sp.cast_min, energy / 8))
            mins -= casts * sp.cast_min; energy -= casts * 8
            self.sell("fish", int(casts * (1 - sp.escape)), self.s.fish_value)   # g per cast: bot measured ~17-20
            self.xp["fishing"] += casts * 8
        return mins, energy

    def access(self, loc):
        if loc == "Desert": return "bus" in self.buildings and self.buildings["bus"] <= self.t
        if loc == "Woods": return self.steel_axe is not None and self.steel_axe <= self.t
        if loc == "UndergroundMine": return self.floor >= 20
        return True

    def desert_trip(self, loc):
        if loc == "Desert":
            self.gold -= 500
            for it in ("Coconut", "Cactus Fruit"):
                if it in self.needed(): self.gold -= 200; self.add(it)
            return True
        return False

    def spawn_forage(self, extras=True):
        tabs = TAB["forage"]
        locs = ["Forest", "Mountain", "Town", "Beach", "BusStop"] + (["Woods"] if self.access("Woods") else [])
        if self.buildings.get("bridge") is not None and self.r.random() < 0.5: self.forage.setdefault("Beach", []).append("Sea Urchin")
        for loc in locs:
            t = tabs.get(loc, {}).get(self.season)
            if not t: continue
            cur = self.forage.setdefault(loc, [])
            n = min(self.r.randint(t["spawn_min"], t["spawn_max"]), t["max_at_once"] - len(cur))
            items, ps = zip(*t["p_item"].items())
            for _ in range(max(0, n)):
                cur.append(self.r.choices(items, ps)[0])
        if extras and self.season == "winter":
            # artifact spots: Winter Root 50%, Snow Yam 20% per spot dug (ASSUMPTION: 1 spot/day dug on tours)
            if self.r.random() < 0.5: self.forage.setdefault("Forest", []).append("Winter Root")
            if self.r.random() < 0.2: self.forage.setdefault("Forest", []).append("Snow Yam")
        if extras and self.season in ("summer", "fall") and self.floor >= 1 and self.r.random() < 0.05:
            self.add("Red Mushroom")

    AREA_ITEMS = {0: ("Quartz", "Earth Crystal", "Slime", "Cave Carrot", "Copper Bar"),
                  40: ("Frozen Tear", "Aquamarine", "Frozen Geode", "Bat Wing", "Solar Essence", "Iron Bar"),
                  80: ("Fire Quartz", "Void Essence", "Purple Mushroom", "Gold Bar")}

    def mine(self, floors, nd):
        """Descend toward the goal (or toward the deepest area a needed item requires); once there, use the
        elevator to farm the area whose items are still needed (real players revisit floors)."""
        need_areas = [a for a, its in self.AREA_ITEMS.items() if any(i in nd for i in its)]
        goal = max([self.p.mine_goal] + [a + 1 for a in need_areas])
        while floors > 0:
            if self.floor < min(goal, 120):
                f = self.floor; self.floor += 1
            else:
                if not need_areas: break
                a = self.r.choice(need_areas); f = a + self.r.randrange(39)   # farm a floor in that area
            area = 0 if f < 40 else (40 if f < 80 else 80)
            for it, ex in MINE_YIELD[area].items():
                k = int(ex) + (1 if self.r.random() < ex - int(ex) else 0)
                self.add(it, k)
            floors -= 1
            self.xp["mining"] += 30
        # geodes -> Clint (25g): 6.25% bundle mineral
        for geo, mn in (("Geode", "Earth Crystal"), ("Frozen Geode", "Frozen Tear"), ("Magma Geode", "Fire Quartz")):
            n = self.inv.get(geo, 0)
            keep = 1 if geo == "Frozen Geode" and "Frozen Geode" in nd else 0
            for _ in range(max(0, n - keep)):
                self.gold -= 25
                if self.r.random() < 0.0625: self.add(mn)
            self.inv[geo] = min(n, keep)
        # bars from ore (5 ore + 1 coal)
        for ore, bar in (("Copper Ore", "Copper Bar"), ("Iron Ore", "Iron Bar"), ("Gold Ore", "Gold Bar")):
            while self.inv.get(ore, 0) >= 5 and self.inv.get("Coal", 0) >= 1 and self.inv.get(bar, 0) < 6:
                self.inv[ore] -= 5; self.inv["Coal"] -= 1; self.add(bar)
            if self.inv.get(ore, 0) > 20: self.sell(ore, self.inv[ore] - 20, PRICE(ore)); self.inv[ore] = 20
        # steel axe for Secret Woods once bars exist (2000+5000g, 4 days)
        if False:
            self.gold -= 7000; self.inv["Iron Bar"] -= 5; self.inv["Copper Bar"] -= 5; self.steel_axe = self.t + 4
            self.log.append((self.t, "steel axe", ""))
        for wood_item in ("Wood", "Stone"):
            pass


TAB = json.load(open(os.path.join(HERE, "data", "tables.json")))
