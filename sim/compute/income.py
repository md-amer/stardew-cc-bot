"""Profit per tile per season for crops buyable in Year 1 (Pierre), planted day 1, base quality, no fertilizer.
Profit = harvests x items x sell - seeds bought. Regrowing crops buy seed once."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gamedata as g
rows = []
for seed, c in g.crops().items():
    if not c["pierre"]: continue
    if c["seed"] in ("Garlic Seeds", "Rice Shoot", "Red Cabbage Seeds", "Artichoke Seeds"): continue  # Y2
    for s in c["seasons"]:
        days = 27  # plant day 1, grows overnight
        if c["regrow"] > 0:
            h = 0 if days < c["grow_days"] else 1 + (days - c["grow_days"]) // c["regrow"]
            if len(c["seasons"]) > 1 and s == c["seasons"][0]:
                days2 = days + 28 * (len(c["seasons"]) - 1)
                h = 1 + (days2 - c["grow_days"]) // c["regrow"]
            buys = 1
        else:
            h = days // c["grow_days"]; buys = h
        items = (c["min_stack"] + c["max_stack"]) / 2 + c["extra_chance"] / (1 - min(.9, c["extra_chance"])) if c["extra_chance"] else (c["min_stack"] + c["max_stack"]) / 2
        profit = h * items * c["sell"] - buys * c["pierre"]
        rows.append((profit, c["crop"], s, h, c["grow_days"], c["regrow"], c["pierre"], c["sell"], c["trellis"]))
rows.sort(reverse=True)
print(f"{'crop':14}{'season':8}{'harvests':>9}{'grow':>5}{'regrow':>7}{'seed':>6}{'sell':>6}{'profit/tile':>12}")
for r in rows[:22]:
    print(f"{r[1]:14}{r[2]:8}{r[3]:9}{r[4]:5}{r[5]:7}{r[6]:6}{r[7]:6}{r[0]:12.0f}{'  trellis' if r[8] else ''}")
