"""Strategy search on World v1 + Rolling planner. OBJECTIVE v2: minimise CC completion day (median, p90 tie-break).
Objective (Amer): maximise P(CC done by Y1 Winter 28). Tie-break: mean bundles done by end of Year 1.
Score = 100 * P(Y1) + mean bundles at day 112 (31 bundles incl. 4 Vault).
Method: random search (common seeds) -> coordinate local search -> validation on 1000 fresh seeds.
"""
import random, sys, json, os, time, math
from multiprocessing import Pool
import world as W, world1 as W1, planner as P

SPACE = {
    "vault_first": [True, False],
    "reserve": [200, 500, 1000],
    "max_tiles": [40, 60, 80, 120, 160],
    "sprinkler_goal": [0, 40, 80, 120, 200],
    "money_spring": ["Potato", "Cauliflower", "Kale", "Parsnip"],
    "money_summer": ["Blueberry", "Melon", "Corn", "Hot Pepper"],
    "money_fall": ["Pumpkin", "Cranberries", "Corn"],
    "fert": [0, 1], "fert_money": [False, True],
    "melon_q": [10, 20, 30, 45], "pumpkin_q": [10, 20, 30, 45], "corn_q": [6, 12, 20],
    "mine_days": [0, 1, 2, 3, 4], "mine_goal": [40, 80, 120], "mine_threshold": [3, 5, 7, 99],
    "chickens": [2, 4, 6], "crab_pots": [0, 1, 3, 5],
    "pig": [False, True], "kitchen": [False, True], "cave": ["bats", "none"],
    "order": ["C-B-BC-DC-A-P", "C-BC-DC-B-A-P", "C-BC-DC-A-B-P", "A-C-BC-DC-B-P", "C-A-BC-DC-B-P", "C-BC-A-DC-B-P", "A-C-B-BC-DC-P"],
    "energy_reserve": [50, 100, 150],
    "max_targets": [1, 2, 3],
}
ORD = {"C": "Coop", "B": "Barn", "BC": "Big Coop", "DC": "Deluxe Coop", "A": "Apple Sapling", "P": "Pomegranate Sapling"}
BASE = {"vault_first": True, "reserve": 500, "max_tiles": 80, "sprinkler_goal": 40, "money_spring": "Potato", "money_summer": "Blueberry",
        "money_fall": "Pumpkin", "fert": 1, "fert_money": False, "melon_q": 30, "pumpkin_q": 30, "corn_q": 12, "mine_days": 2,
        "mine_goal": 80, "mine_threshold": 7, "chickens": 4, "crab_pots": 3, "pig": False, "kitchen": False, "cave": "bats",
        "order": "C-B-BC-DC-A-P", "energy_reserve": 100, "max_targets": 2}


def to_plan(k):
    p = W.Plan()
    p.vault_first, p.reserve, p.max_tiles, p.sprinkler_goal = k["vault_first"], k["reserve"], k["max_tiles"], k["sprinkler_goal"]
    p.money_crop = {"spring": k["money_spring"], "summer": k["money_summer"], "fall": k["money_fall"]}
    p.fert, p.fert_money = k["fert"], k["fert_money"]
    p.crops = {"spring": {"Parsnip": 2, "Green Bean": 2, "Cauliflower": 2, "Potato": 2},
               "summer": {"Melon": k["melon_q"], "Tomato": 2, "Hot Pepper": 2, "Blueberry": 2, "Corn": k["corn_q"], "Sunflower": 2, "Poppy": 2, "Wheat": 12, "Red Cabbage": 2},
               "fall": {"Pumpkin": k["pumpkin_q"], "Eggplant": 2, "Yam": 2, "Corn": 2, "Sunflower": 2}}
    p.mine_days_per_week, p.mine_goal = k["mine_days"], k["mine_goal"]
    p.chickens, p.crab_pots, p.pig, p.kitchen, p.cave = k["chickens"], k["crab_pots"], k["pig"], k["kitchen"], k["cave"]
    p.build_order = [ORD[x] for x in k["order"].split("-")]
    return p


def one(args):
    k, seed, speeds, cap = args
    cap = CAP
    sp = {"bot": W.BOT, "human": W.HUMAN}[speeds] if isinstance(speeds, str) else speeds
    w = W1.World1(to_plan(k), sp, seed=seed, planner=P.Rolling(max_targets=k["max_targets"], mine_threshold=k["mine_threshold"]))
    w.target_energy_reserve = k["energy_reserve"]
    t = w.run(cap)
    by_y1 = sum(1 for d in w.done.values() if d < 112)
    return (t is not None and t < 112, by_y1, t if t is not None else CAP + 150)


CAP = 336


def score(pool, k, seeds, speeds, cap=None):
    """Minimise completion time: higher score = better = -(median + 0.25 x (p90 - median))."""
    r = pool.map(one, [(k, s, speeds, CAP) for s in seeds])
    d = sorted(x[2] for x in r)
    med, p90 = d[len(d) // 2], d[int(.9 * len(d))]
    return -(med + 0.25 * (p90 - med)), med, p90


def D(t): return "not done in 3 years" if t > CAP else f"Y{t//112+1} {W.SE[(t//28)%4]} {t%28+1}"


def wilson(p, n, z=1.96):
    d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0, (c - h) / d), min(1, (c + h) / d)


if __name__ == "__main__":
    speeds = "human" if "human" in sys.argv else "bot"
    N = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 150
    rng = random.Random(5); seeds = list(range(200, 300)); t0 = time.time()
    with Pool(7) as pool:
        cands = [(score(pool, BASE, seeds, speeds), BASE)]
        print(f"[{speeds}] baseline: median {D(cands[0][0][1])}, p90 {D(cands[0][0][2])}", flush=True)
        for i in range(N):
            k = {a: rng.choice(v) for a, v in SPACE.items()}
            cands.append((score(pool, k, seeds, speeds), k))
            if i % 25 == 24:
                b = max(cands, key=lambda x: x[0][0])
                print(f"  random {i+1}/{N}: best median {D(b[0][1])}, p90 {D(b[0][2])} ({time.time()-t0:.0f}s)", flush=True)
        cands.sort(key=lambda x: -x[0][0])
        best = cands[0]
        for start in cands[:2]:
            cur = start; improved = True
            while improved:
                improved = False
                for knob, vals in SPACE.items():
                    for v in vals:
                        if v == cur[1][knob]: continue
                        k2 = dict(cur[1]); k2[knob] = v
                        sc = score(pool, k2, seeds, speeds)
                        if sc[0] > cur[0][0] + 0.5:
                            cur = (sc, k2); improved = True
                            print(f"  local: {knob}={v} -> median {D(sc[1])}, p90 {D(sc[2])}", flush=True)
            if cur[0][0] > best[0][0]: best = cur
        vs = list(range(10000, 11000))
        val = score(pool, best[1], vs, speeds); bval = score(pool, BASE, vs, speeds)
    out = {"speeds": speeds, "objective": "min CC day", "best": best[1], "best_val": {"median": val[1], "p90": val[2]},
           "base_val": {"median": bval[1], "p90": bval[2]}, "top10": [[c[0], c[1]] for c in cands[:10]]}
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", f"opt2_{speeds}.json"), "w"), indent=1)
    print(f"\n[{speeds}] BEST on 1000 fresh seeds: median {D(val[1])} (day {val[1]}), p90 {D(val[2])}")
    print(f"[{speeds}] BASELINE same seeds:      median {D(bval[1])} (day {bval[1]}), p90 {D(bval[2])}")
    print("best knobs:", json.dumps(best[1])); print(f"total {time.time()-t0:.0f}s")
