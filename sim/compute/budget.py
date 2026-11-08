"""Gold budget for the Year 1 route. Prices from data (Y1 wood 10g, stone 20g at Robin)."""
WOOD, STONE = 10, 20  # buy price Y1; 0 if chopped/mined
items = [
 ("Vault 2.5k+5k+10k+25k",            42500, 0, 0),
 ("Construction bundle 198 wood 99 stone", 0, 198, 99),
 ("Coop",                              4000, 300, 100),
 ("Big Coop",                         10000, 400, 150),
 ("Deluxe Coop",                      20000, 500, 200),
 ("4 chickens (both colours 87.5%)",   1600, 0, 0),
 ("Duck",                              600, 0, 0),
 ("Rabbit",                            4000, 0, 0),
 ("Barn",                              6000, 350, 150),
 ("Cow",                               750, 0, 0),
 ("Milk Pail",                         1000, 0, 0),
 ("Apple sapling (Fodder apples)",     4000, 0, 0),
 ("Maki Roll at Gus",                   300, 0, 0),
 ("Hay x10 at Marnie",                  500, 0, 0),
]
optional = [
 ("Pig path for Truffle: Big Barn+Deluxe Barn+Pig", 12000+25000+8000, 450+550, 200+300),
 ("House upgrade (kitchen) for Fried Egg",          10000, 450, 0),
 ("Goat path: Big Barn + Goat",                     14000, 450, 200),
]
def show(rows, title):
    g = sum(r[1] for r in rows); w = sum(r[2] for r in rows); s = sum(r[3] for r in rows)
    print(f"== {title}")
    for r in rows: print(f"  {r[0]:48} {r[1]:7,}g  wood {r[2]:4}  stone {r[3]:4}")
    print(f"  TOTAL gold {g:,}  + wood {w} (buy {w*WOOD:,}g) + stone {s} (buy {s*STONE:,}g) = {g+w*WOOD+s*STONE:,}g if all bought")
    return g + w*WOOD + s*STONE
base = show(items, "Required Year 1 route")
show(optional, "Optional chains")
print(f"\nWood price Y2+ is 50g, stone 100g: same wood/stone in Y2 costs {sum(r[2] for r in items)*50 + sum(r[3] for r in items)*100:,}g instead of {sum(r[2] for r in items)*10 + sum(r[3] for r in items)*20:,}g")
