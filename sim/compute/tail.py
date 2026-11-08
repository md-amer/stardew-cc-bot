"""Games not finished in 3 years: which items are still missing?"""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from multiprocessing import Pool
import world as W, world1 as W1, planner as P, optimize2 as O
def run(a):
    k, s, sp = a
    w = W1.World1(O.to_plan(k), sp, seed=s, planner=P.Rolling(max_targets=k["max_targets"], mine_threshold=k["mine_threshold"]))
    w.target_energy_reserve = k["energy_reserve"]; t = w.run(336)
    miss = []
    for b, v in w.slots.items():
        if b in w.done: continue
        for i, (nm, q, ql) in enumerate(v["items"]):
            if i not in v["got"]: miss.append(f"{b}:{nm}{'*' if ql == 2 else ''}")
    return t, miss
if __name__ == "__main__":
  for sp_name, sp in (("human", W.HUMAN), ("bot", W.BOT)):
      k = json.load(open(f"data/opt2_{sp_name}.json"))["best"]
      with Pool(7) as pool: r = pool.map(run, [(k, s, sp) for s in range(7000, 7200)])
      un = [m for t, m in r if t is None]
      c = collections.Counter(x for m in un for x in m)
      print(f"[{sp_name}] unfinished {len(un)}/200; missing items in unfinished games:", c.most_common(12))
