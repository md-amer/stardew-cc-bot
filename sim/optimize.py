"""Strategy search for the fastest Community Center completion.

Method:
1. Random search: N random strategies, each run on the same K seeds (common random numbers, so
   differences come from the strategy, not luck).
2. Local search: from the best few, change one knob at a time; keep changes that improve the score.
3. Validation: best strategy on 40 fresh seeds.
Score = median completion day + 0.5 x (90th percentile - median). Unfinished runs count as cap + 200.
"""
import random, sys, json, copy, os, time
from multiprocessing import Pool
import world as W

CAP = 336
SPACE = {
    "vault_first": [True, False],
    "reserve": [200, 500, 1000, 2000],
    "max_tiles": [40, 60, 80, 120, 160],
    "sprinkler_goal": [0, 40, 80, 120, 200],
    "money_spring": ["Potato", "Cauliflower", "Kale", "Parsnip"],
    "money_summer": ["Blueberry", "Melon", "Corn", "Hot Pepper"],
    "money_fall": ["Pumpkin", "Cranberries", "Corn"],
    "fert": [0, 1], "fert_money": [False, True],
    "melon_q": [0, 10, 20, 30, 45], "pumpkin_q": [0, 10, 20, 30, 45], "corn_q": [0, 6, 12, 20],
    "mine_days": [0, 1, 2, 3, 4], "mine_goal": [40, 80, 120],
    "chickens": [2, 4, 6], "crab_pots": [0, 1, 3, 5],
    "pig": [False, True], "kitchen": [False, True], "cave": ["bats", "none"],
    "order": ["C-B-BC-DC-A-P", "C-BC-DC-B-A-P", "C-BC-DC-A-B-P", "A-C-BC-DC-B-P", "C-B-A-BC-DC-P", "C-BC-B-DC-A"],
}
ORD = {"C": "Coop", "B": "Barn", "BC": "Big Coop", "DC": "Deluxe Coop", "A": "Apple Sapling", "P": "Pomegranate Sapling"}


def to_plan(k):
    p = W.Plan()
    p.vault_first, p.reserve, p.max_tiles, p.sprinkler_goal = k["vault_first"], k["reserve"], k["max_tiles"], k["sprinkler_goal"]
    p.money_crop = {"spring": k["money_spring"], "summer": k["money_summer"], "fall": k["money_fall"]}
    p.fert, p.fert_money = k["fert"], k["fert_money"]
    p.crops = {"spring": {"Parsnip": 2, "Green Bean": 2, "Cauliflower": 2, "Potato": 2},
               "summer": {"Melon": max(2, k["melon_q"]), "Tomato": 2, "Hot Pepper": 2, "Blueberry": 2, "Corn": max(2, k["corn_q"]),
                          "Sunflower": 2, "Poppy": 2, "Wheat": 12},
               "fall": {"Pumpkin": max(2, k["pumpkin_q"]), "Eggplant": 2, "Yam": 2, "Corn": 2, "Sunflower": 2}}
    p.mine_days_per_week, p.mine_goal = k["mine_days"], k["mine_goal"]
    p.chickens, p.crab_pots, p.pig, p.kitchen, p.cave = k["chickens"], k["crab_pots"], k["pig"], k["kitchen"], k["cave"]
    p.build_order = [ORD[x] for x in k["order"].split("-")]
    return p


def one(args):
    k, seed, speeds = args
    w = W.World(to_plan(k), W.HUMAN if speeds == "human" else W.BOT, seed=seed)
    t = w.run(CAP)
    return t if t is not None else CAP + 200


def score(pool, k, seeds, speeds):
    r = sorted(pool.map(one, [(k, s, speeds) for s in seeds]))
    med, p90 = r[len(r) // 2], r[int(.9 * len(r))]
    return med + 0.5 * (p90 - med), med, p90


def rand_k(rng): return {a: rng.choice(v) for a, v in SPACE.items()}


def date(t): return "not done" if t > CAP else f"Y{t//112+1} {W.SE[(t//28)%4]} {t%28+1}"


if __name__ == "__main__":
    speeds = "human" if "human" in sys.argv else "bot"
    N = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 120
    rng = random.Random(11)
    seeds = list(range(100, 108))
    out = {"speeds": speeds, "history": []}
    t0 = time.time()
    with Pool(7) as pool:
        base = {"vault_first": True, "reserve": 500, "max_tiles": 80, "sprinkler_goal": 60 if 60 in SPACE["sprinkler_goal"] else 40,
                "money_spring": "Potato", "money_summer": "Blueberry", "money_fall": "Pumpkin", "fert": 1, "fert_money": False,
                "melon_q": 30, "pumpkin_q": 30, "corn_q": 12, "mine_days": 2, "mine_goal": 80, "chickens": 4, "crab_pots": 3,
                "pig": False, "kitchen": False, "cave": "bats", "order": "C-B-BC-DC-A-P"}
        cands = [(score(pool, base, seeds, speeds), base)]
        print(f"baseline: score {cands[0][0][0]:.0f} median {date(cands[0][0][1])} p90 {date(cands[0][0][2])}", flush=True)
        for i in range(N):
            k = rand_k(rng); sc = score(pool, k, seeds, speeds); cands.append((sc, k))
            if i % 20 == 19:
                b = min(cands, key=lambda x: x[0][0])
                print(f"random {i+1}/{N}: best score {b[0][0]:.0f} median {date(b[0][1])}  ({time.time()-t0:.0f}s)", flush=True)
        cands.sort(key=lambda x: x[0][0])
        # local search from top 3
        best = cands[0]
        for start in cands[:3]:
            cur = start
            improved = True
            while improved:
                improved = False
                for knob, vals in SPACE.items():
                    for v in vals:
                        if v == cur[1][knob]: continue
                        k2 = dict(cur[1]); k2[knob] = v
                        sc = score(pool, k2, seeds, speeds)
                        if sc[0] < cur[0][0] - 0.5:
                            cur = (sc, k2); improved = True
                            print(f"  local: {knob}={v} -> score {sc[0]:.0f} median {date(sc[1])}", flush=True)
            if cur[0][0] < best[0][0]: best = cur
        # validation on fresh seeds
        val = score(pool, best[1], list(range(1000, 1040)), speeds)
        bval = score(pool, base, list(range(1000, 1040)), speeds)
    out["best"] = best[1]; out["best_val"] = {"score": val[0], "median": val[1], "p90": val[2]}
    out["base_val"] = {"score": bval[0], "median": bval[1], "p90": bval[2]}
    out["top10"] = [(c[0], c[1]) for c in cands[:10]]
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", f"opt_{speeds}.json"), "w"), indent=1, default=str)
    print(f"\nBEST ({speeds}) on 40 fresh seeds: median {date(val[1])}, p90 {date(val[2])}")
    print(f"BASELINE on same seeds: median {date(bval[1])}, p90 {date(bval[2])}")
    print("best knobs:", json.dumps(best[1]))
    print(f"total {time.time()-t0:.0f}s")
