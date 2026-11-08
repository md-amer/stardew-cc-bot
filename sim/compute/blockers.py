"""Which bundles/items miss Year 1 under the best strategies, and what each bot speed fix is worth."""
import sys, os, json, collections, dataclasses
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from multiprocessing import Pool
import world as W, world1 as W1, planner as P, optimize1 as O

def run(args):
    k, seed, sp = args
    w = W1.World1(O.to_plan(k), sp, seed=seed, planner=P.Rolling(max_targets=k["max_targets"], mine_threshold=k["mine_threshold"]))
    w.target_energy_reserve = k["energy_reserve"]; w.run(112)
    miss_b = [b for b in w.slots if b not in w.done]
    miss_i = []
    for b in miss_b:
        v = w.slots[b]
        for i, (nm, q, ql) in enumerate(v["items"]):
            if i not in v["got"]: miss_i.append(nm + ("*" if ql == 2 else ""))
    return miss_b, miss_i, len(w.done) == len(w.slots)

def report(k, sp, label, n=300):
    with Pool(7) as pool: r = pool.map(run, [(k, s, sp) for s in range(5000, 5000 + n)])
    mb = collections.Counter(b for x in r for b in x[0]); p = sum(x[2] for x in r) / n
    print(f"== {label}: P(Y1) {p:.1%}; bundles missing at Y1 end (share of runs):")
    print("   ", ", ".join(f"{b} {c/n:.0%}" for b, c in mb.most_common(10)))
    return p

if __name__ == "__main__":
    hb = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "opt1_human.json")))["best"]
    bb = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "opt1_bot.json")))["best"]
    report(bb, W.BOT, "bot speeds, best bot strategy")
    report(hb, W.HUMAN, "human speeds, best human strategy")
    print("\nValue of each bot fix (bot speeds, one parameter set to human value, best human strategy):")
    base = report(hb, W.BOT, "bot speeds, best human strategy", 300)
    for f in ["overhead", "water_min", "plant_min", "cast_min", "floors_per_hour", "forage_tour_min", "fish_value", "escape"]:
        sp = dataclasses.replace(W.BOT, **{f: getattr(W.HUMAN, f)})
        p = report(hb, sp, f"fix {f}: {getattr(W.BOT, f)} -> {getattr(W.HUMAN, f)}", 300)
