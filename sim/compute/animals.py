"""Days from purchase to first deluxe product, FarmAnimal.cs:1015-1030 exact rolls.
Assumes: petted daily (+15), fed (fullness 255), happiness 255 (petted + fed + not cold), daily luck U(-0.1,0.1).
Grass bonus (+8) ignored (conservative). Baby until DaysToMature."""
import random, statistics as st, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gamedata as g

def run(animal, n=20000, seed=3):
    a = g.raw("FarmAnimals")[animal]
    div = a.get("DeluxeProduceCareDivisor", 1200.0); minf = a.get("DeluxeProduceMinimumFriendship", 200) if "DeluxeProduceMinimumFriendship" in a else 0
    lm = a.get("DeluxeProduceLuckMultiplier", 0.0); dtp = a.get("DaysToProduce", 1); mat = a.get("DaysToMature", 0) or 0
    rng = random.Random(seed); out = []; first_any = []
    for _ in range(n):
        f = 0; since = 0; hap = 255
        for day in range(1, 400):
            f = min(1000, f + 15)          # petting today
            since += 1                      # overnight DayUpdate
            if day <= mat: continue
            luck = rng.randint(-100, 100) / 1000
            if since >= dtp and rng.random() < 255 / 200 and rng.random() < hap / 70:
                if not first_any: pass
                deluxe = False
                if rng.random() < hap / 150:
                    bonus = hap * 1.5 if hap > 200 else 0
                    if f >= minf and rng.random() < (f + bonus) / div + luck * lm:
                        deluxe = True
                    since = 0
                if deluxe:
                    out.append(day); break
    return out

for an, item in [("White Chicken", "Large Egg"), ("Brown Chicken", "Large Egg (brown)"), ("White Cow", "Large Milk"),
                 ("Goat", "L. Goat Milk"), ("Duck", "Duck Feather"), ("Rabbit", "Rabbit's Foot")]:
    d = sorted(run(an))
    q = lambda p: d[int(p * len(d))]
    print(f"{an:14} {item:18} days after purchase: median {st.median(d):5.0f}  80% {q(.8):4d}  95% {q(.95):4d}")
