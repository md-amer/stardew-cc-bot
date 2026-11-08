"""Random sources over time: fruit bats (FarmCave.cs:216) and Travelling Cart (3.0%/item/visit, Fri+Sun)."""
import random, statistics as st
rng = random.Random(7)
FRUITS = ["Apricot", "Orange", "Peach", "Pomegranate", "Cherry"]

def bats_day():
    out = []
    while rng.random() < 0.66:
        r = rng.randrange(5)
        if r == 0: out.append("Salmonberry")
        elif r == 1: out.append("Spice Berry")
        elif r == 2: out.append("Wild Plum")
        elif r == 3: out.append("Blackberry")
        else: out.append("Apple" if rng.random() < 0.1 else FRUITS[rng.randrange(5)])
    return out

def days_until(goal, n=5000):
    res = []
    for _ in range(n):
        have = {}
        for d in range(1, 2000):
            for it in bats_day(): have[it] = have.get(it, 0) + 1
            if all(have.get(k, 0) >= v for k, v in goal.items()):
                res.append(d); break
    res.sort(); return st.median(res), res[int(.9 * len(res))]

goals = {
 "Artisan fruits x6 kinds (5 fruits + Apple)": {f: 1 for f in FRUITS} | {"Apple": 1},
 "2 bat fruits for Artisan (any 2 kinds)": None,
 "Pomegranate x2 (Artisan + Enchanter)": {"Pomegranate": 2},
 "Apple x3 (Fodder)": {"Apple": 3},
 "Apple x4 (Fodder + Artisan)": {"Apple": 4},
 "Spice Berry + Wild Plum + Blackberry": {"Spice Berry": 1, "Wild Plum": 1, "Blackberry": 1},
}
for k, gl in goals.items():
    if gl is None:
        res = []
        for _ in range(5000):
            kinds = set()
            for d in range(1, 500):
                kinds |= {x for x in bats_day() if x in FRUITS + ["Apple"]}
                if len(kinds) >= 2: res.append(d); break
        res.sort(); print(f"bats: {k:45} median {st.median(res):5.0f} d   90% {res[int(.9*len(res))]:4d} d"); continue
    m, p90 = days_until(gl)
    print(f"bats: {k:45} median {m:5.0f} d   90% {p90:4d} d")

p = 10 / 334
for visits in (8, 16, 24, 32):
    print(f"cart: P(specific item seen in {visits:2d} visits) = {1-(1-p)**visits:.0%}   either of 2 items (cabbage or seeds): {1-(1-2*p)**visits:.0%}")
