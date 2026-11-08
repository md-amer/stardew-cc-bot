"""Run a plan over many seeds; report completion-date distribution and last bundles."""
import sys, statistics as st, collections, json
import world as W

def date(t): return "never" if t is None else f"Y{t//112+1} {W.SE[(t//28)%4]} {t%28+1}"

def evaluate(plan, speeds=W.BOT, seeds=range(20), cap=336, verbose=False):
    fins, lastb, bdays = [], collections.Counter(), collections.defaultdict(list)
    worlds = []
    for s in seeds:
        w = W.World(plan, speeds, seed=s); t = w.run(cap)
        fins.append(t if t is not None else cap + 100)
        for b, d in w.done.items(): bdays[b].append(d)
        missing = [b for b in w.slots if b not in w.done]
        for b in missing: lastb[b] += 1
        if t is not None:
            lastb["LAST:" + max(w.done, key=w.done.get)] += 1
        worlds.append(w)
    fins.sort()
    res = {"median": fins[len(fins)//2], "p90": fins[int(.9*len(fins))], "done_rate": sum(f <= cap for f in fins)/len(fins)}
    if verbose:
        print(f"completion median {date(res['median'] if res['median']<=cap else None)}  p90 {date(res['p90'] if res['p90']<=cap else None)}  finished {res['done_rate']:.0%}")
        print("bundle median day:")
        for b, v in sorted(bdays.items(), key=lambda x: st.median(x[1])):
            print(f"   {b:16} {date(int(st.median(v))):16} ({len(v)}/{len(list(seeds))} runs)")
        print("never finished (count of runs):", {k: v for k, v in lastb.items() if not k.startswith('LAST')})
        print("last bundle:", {k[5:]: v for k, v in lastb.items() if k.startswith('LAST')})
    return res, worlds

if __name__ == "__main__":
    sp = W.HUMAN if "human" in sys.argv else W.BOT
    res, ws = evaluate(W.Plan(), sp, range(int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 20), verbose=True)
    w = ws[0]
    print("seed0 log (first 40):", [(date(t), k, v) for t, k, v in w.log[:40]])
    print("seed0 end gold", w.gold, "earned", w.earned, "floor", w.floor, "levels", {k: w.level(k) for k in w.xp})
