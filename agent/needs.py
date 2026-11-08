"""What the Community Center still needs. Items on this list are never shipped; they go to the chest.

Live source: the mod's `cc` endpoint (same info the Junimo notes show: done/missing ingredients,
which rooms have a readable note). Fallback when the game is unreachable: bundles.json (wiki).
Room unlock rule (decompiled CommunityCenter.shouldNoteAppearInArea): Crafts Room always;
Pantry + Fish Tank after 1 complete bundle; Boiler Room 2; Bulletin Board 3; Vault 4.
"""
import json, os
B = json.load(open(os.path.join(os.path.dirname(__file__), "bundles.json")))
MONEY = {"2,500 Bundle", "5,000 Bundle", "10,000 Bundle", "25,000 Bundle", "Quality Crops Bundle"}  # quality = gold only, handled separately
ROOM_THRESHOLD = {"Crafts Room": 0, "Pantry": 1, "Fish Tank": 1, "Boiler Room": 2, "Bulletin Board": 3, "Vault": 4}

def needed_counts(done_bundles=()):
    need = {}
    for b, v in B.items():
        if b in MONEY or b in done_bundles:
            continue
        for it in v["items"]:
            need[it["name"]] = need.get(it["name"], 0) + it["qty"]
    return need

NEED = needed_counts()          # static fallback


def live():
    """Bundle state from the game, or None if the game is unreachable."""
    try:
        import sv
        return sv.call("cc")
    except Exception:
        return None


def _open_bundles(cc):
    """Incomplete bundles with item ingredients (gold-only Vault bundles skipped)."""
    for b in cc["bundles"]:
        if b["complete"]:
            continue
        ings = [g for g in b["ingredients"] if g["name"] != "Gold"]
        if ings:
            yield b, ings


def quota(cc=None):
    """name -> how many to keep for still-missing ingredients (all rooms, open or not).
    Quality > normal is skipped: the agent cannot pick crop/fish quality."""
    cc = cc or live()
    if not cc:
        return dict(NEED)
    q = {}
    for b, ings in _open_bundles(cc):
        for g in ings:
            if not g["done"] and g["quality"] == 0:
                q[g["name"]] = q.get(g["name"], 0) + g["stack"]
    return q


def quality_holds(cc=None):
    """name -> (min quality, stack) for still-missing quality ingredients (e.g. 5 gold Melons)."""
    cc = cc or live()
    out = {}
    for b, ings in _open_bundles(cc or {"bundles": []}):
        for g in ings:
            if not g["done"] and g["quality"] > 0:
                out[g["name"]] = (g["quality"], g["stack"])
    return out

def donation_plan(have, cc=None, have_q=None):
    """have: name -> stack (backpack + chest). Returns (names to bring, rooms to visit).
    Includes rooms that will open after this trip's completed bundles (thresholds above)."""
    cc = cc or live()
    if not cc:
        return set(), []
    done_n = cc["completeBundles"]
    per_bundle = []
    for b, ings in _open_bundles(cc):
        missing = [g for g in ings if not g["done"]]
        filled = sum(1 for g in ings if g["done"])
        hq = have_q or {}
        can = [g for g in missing if (g["quality"] == 0 and have.get(g["name"], 0) >= g["stack"])
               or (g["quality"] > 0 and max((n for q, n in hq.get(g["name"], {}).items() if int(q) >= g["quality"]), default=0) >= g["stack"])]
        completes = filled + len(can) >= b["slots"]
        per_bundle.append((b, can, completes))
    # completions in already-open rooms raise the count; repeat until no new room opens
    open_rooms = {b["room"] for b in cc["bundles"] if b["open"]}
    while True:
        n = done_n + sum(1 for b, can, c in per_bundle if c and b["room"] in open_rooms)
        new = {r for r, t in ROOM_THRESHOLD.items() if n >= t} - open_rooms
        if not new:
            break
        open_rooms |= new
    bring, rooms = set(), []
    for b, can, _ in per_bundle:
        if b["room"] in open_rooms and can:
            bring |= {g["name"] for g in can}
            if b["room"] not in rooms:
                rooms.append(b["room"])
    # visit rooms in unlock order so newly opened notes are read after the completing bundle
    rooms.sort(key=lambda r: ROOM_THRESHOLD.get(r, 9))
    return bring, rooms


def is_needed(name, cc=None):
    return name in quota(cc)
