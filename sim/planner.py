"""Nightly planner: builds tomorrow's agenda from live state + forecast.

Rolling (deadline-slack) planner:
- chores first (water unsprinkled tiles, animals),
- then targets ranked by urgency = 1 / (days left in the item's window this year + 1), boosted when today's
  weather is the rare kind the item needs (rain-only fish on a rain day),
- errands only when they do something (shop with spare gold, Gus for Maki/Fried Egg, cart Fri/Sun, CC when
  something can be donated or paid),
- mining when a mine item/floor goal is open and it is a mine day (or a mine item is urgent),
- leftover time: money fishing.
"""
import fishsim as fs
import world1 as W1
from world1 import Task

MINE_FLOOR = {"Quartz": 1, "Earth Crystal": 1, "Copper Bar": 1, "Slime": 1, "Cave Carrot": 1,
              "Frozen Tear": 40, "Aquamarine": 40, "Frozen Geode": 40, "Bat Wing": 40, "Solar Essence": 40, "Iron Bar": 40,
              "Fire Quartz": 80, "Void Essence": 80, "Gold Bar": 80, "Purple Mushroom": 80}
SEASON_END = {"spring": 27, "summer": 55, "fall": 83, "winter": 111}


def days_left(w, seasons):
    """Days until this item's last available day this year (from today)."""
    ty = w.t % 112
    ends = [SEASON_END[s] for s in seasons if SEASON_END[s] >= ty]
    return (min(ends) - ty) if ends else 999


def fish_window(fish):
    fid = fs.g.id_by_name().get(fish)
    f = fs.FISH.get(fid)
    if not f or f["trap"]: return (600, 2600)
    a, b = f["times"][0]
    return (a, min(b, 2600))


class Rolling:
    def __init__(self, max_targets=2, mine_threshold=7):
        self.max_targets = max_targets
        self.mine_threshold = mine_threshold

    def plan(self, w):
        A = []
        nd = w.needed()
        dry = w.dry_tiles()
        if dry and w.w != "rain" and w.season != "winter":
            A.append(Task("water", "farm", dry * w.s.water_min, energy=2 * dry, run=lambda w, d: w.do_water(d)))
        if getattr(w, "plant_debt", 0):
            A.append(Task("plant", "farm", w.plant_debt, energy=2 * w.plant_debt / max(w.s.plant_min, 0.1)))
        if w.animals:
            A.append(Task("animals", "farm", len(w.animals) * w.s.animal_min, run=lambda w, d: w.do_animals(d)))
        if w.dow() in (4, 6) and w.gold > w.res() + 300:
            A.append(Task("cart", "cart", 10, run=lambda w, d: w.do_cart(d)))
        place = w.want_shop()
        if place:
            A.append(Task("shop", place, 15, earliest=900, run=lambda w, d: w.do_shop(d)))
        # ---- fish targets
        cands = []
        for fish, slots in w.fishtab.items():
            if fish not in nd: continue
            seasons = sorted({s["season"] for s in slots})
            dl = days_left(w, seasons)
            for sl in slots:
                if sl["season"] != w.season: continue
                if (sl["weather"] == "rain") != (w.w == "rain"): continue
                place = W1.SPOT_PLACE.get((sl["loc"], sl["area"]))
                if not place or not w.access(sl["loc"]) or sl["loc"] == "Desert": continue
                rare = 3.0 if sl["weather"] == "rain" else 1.0
                cands.append((rare * sl["p"] / (dl + 1), fish, sl, place))
        cands.sort(key=lambda x: -x[0])
        used = set()
        for sc, fish, sl, place in cands:
            if fish in used or len(used) >= self.max_targets: continue
            used.add(fish)
            a, b = fish_window(fish)
            A.append(Task("fish:" + fish, place, 180, energy=8 * 9, earliest=a, latest=b, min_dur=w.s.cast_min * 2,
                          run=w.do_fish(fish, sl["p"])))
        # ---- forage
        for loc, items in w.forage.items():
            if any(i in nd for i in items):
                place = {"Forest": "forest_river", "Mountain": "mountain_lake", "Town": "town_river", "Beach": "beach",
                         "BusStop": "busstop", "Woods": "woods"}.get(loc)
                if place: A.append(Task("forage:" + loc, place, w.s.forage_tour_min * 20 / 90, run=w.do_forage(loc)))
        town_trip = any(t.place in ("pierre", "robin", "clint") for t in A) or w.can_handin()
        if ("Maki Roll" in nd and w.gold > 300 + w.res()) or ("Fried Egg" in nd and town_trip and w.gold > 400 + w.res()):
            A.append(Task("gus", "gus", 5, earliest=1200, run=lambda w, d: w.do_gus(d)))
        # axe upgrades (Secret Woods access) and hardwood
        woods_need = any(i in nd for i in ("Hardwood", "Woodskip", "Morel", "Fiddlehead Fern"))
        if woods_need and w.want_clint():
            A.append(Task("clint", "clint", 10, earliest=900, run=lambda w, d: w.do_clint(d)))
        if "Hardwood" in nd and w.access("Woods"):
            A.append(Task("hardwood", "woods", 40, energy=40, run=lambda w, d: w.do_hardwood(d)))
        # ---- desert (whole afternoon)
        desert_need = [i for i in ("Coconut", "Cactus Fruit", "Sandfish") if i in nd]
        if desert_need and w.access("Desert") and w.gold > 1000 + w.res():
            A.append(Task("desert", "busstop", w.s.desert_trip_min, earliest=1000, min_dur=w.s.desert_trip_min * 0.7, run=lambda w, d: w.do_desert(w, d)))
        # ---- CC visit if something to hand in
        if w.can_handin():
            A.append(Task("cc", "cc", 10, earliest=800, run=lambda w, d: w.do_cc(d)))
        # ---- mining or money
        mine_need = [i for i in nd if i in MINE_FLOOR]
        goal_open = w.floor < w.p.mine_goal or mine_need
        if goal_open and w.t >= 4 and (w.dow() < w.p.mine_days_per_week or len(mine_need) >= self.mine_threshold):
            A.append(Task("mine", "mine", 600, energy=200, min_dur=60, run=lambda w, d: w.do_mine(w, d)))
        elif w.season != "winter" or True:
            A.append(Task("money_fish", "forest_river", 600, energy=8 * 30, min_dur=40, run=lambda w, d: w.do_money_fish(w, d)))
        # order: time windows first, CC late, mining/money last
        def key(t):
            if t.name in ("water", "animals", "plant"): return (0, 0)
            if t.name in ("mine", "money_fish"): return (9, 0)
            if t.name == "cc": return (8, 0)
            return (1, t.earliest)
        A.sort(key=key)
        return A
