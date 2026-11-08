"""Quality Crops bundle: 5 gold-star each of 3 of {Parsnip, Melon, Pumpkin, Corn}.
Gold chance (Crop.cs:565): p = 0.2*L/10 + 0.2*f*(L+2)/12 + 0.01, f = fertilizer level (0 none, 1 basic, 2 quality, 3 deluxe).
Deluxe (f>=3): first roll iridium at p/2, then gold at p (iridium counts as gold+ for bundles: quality>=2 accepted).
Question: how many plants N give >=95% chance of >=5 gold?"""
from math import comb, log

def p_gold(L, f):
    p = 0.2 * L / 10 + 0.2 * f * (L + 2) / 12 + 0.01
    if f >= 3:
        return p / 2 + (1 - p / 2) * p
    return p

def n_for(p, k=5, conf=0.95):
    n = k
    while True:
        tail = sum(comb(n, i) * p**i * (1 - p)**(n - i) for i in range(k))
        if 1 - tail >= conf:
            return n
        n += 1

print("gold chance / plants needed for 95% sure of 5 gold")
print("L  | none        | basic       | quality     | deluxe")
for L in range(0, 11):
    row = []
    for f in range(4):
        p = p_gold(L, f)
        row.append(f"{p:5.1%} n={n_for(p):3d}")
    print(f"{L:2d} | " + " | ".join(row))

# farming XP per harvest: 16*ln(0.018*price+1) (Crop.cs:692)
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gamedata as g
XP = [100, 380, 770, 1300, 2150, 3300, 4800, 6900, 10000, 15000]
print("\nfarming XP per harvest and harvests to reach a level (single crop)")
for c in ["Parsnip", "Potato", "Cauliflower", "Green Bean", "Kale", "Melon", "Blueberry", "Hot Pepper", "Corn", "Pumpkin", "Cranberries", "Wheat"]:
    pr = g.obj(g.id_by_name()[c])["Price"]
    xp = int(16 * log(0.018 * pr + 1))
    print(f"{c:12} price {pr:4d} xp {xp:3d}  ->  L2 {380//xp+1:4d}  L4 {1300//xp+1:4d}  L6 {3300//xp+1:4d}  L8 {6900//xp+1:5d}")
