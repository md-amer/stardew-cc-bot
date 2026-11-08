# Computation results (planning only)

Each result names its script in `sim/compute/`. Inputs are in `NUMBERS.md`. All are reproducible:
`python3 compute/<name>.py`.

## 1. Fishing timetable (`fish_timetable.py`, uses `fishsim.py`)
Method: Monte Carlo copy of GameLocation.GetFishFromLocationData (precedence order, chance roll, time,
weather, level and depth weight). 9 spots x 4 seasons x sun/rain x 20 hours x levels 2 and 6, 3,000 casts
each. Game minutes = 20 / p (our bot's measured median 20 game minutes per cast). Escapes not modelled.
Check against our Mountain catches: Bullhead, Carp, Chub and Algae shares match within a few points;
Largemouth Bass lower in our run (escapes, mixed seasons).

| Fish | best slot (level 6) | p/cast | ~game min |
|---|---|---|---|
| Sandfish | Desert top pond, any season | 0.53 | 38 |
| Carp | Woods, any | 0.48 | 42 |
| Sardine | Beach, spring/fall/winter | 0.42 | 48 |
| Bream | Town river, night | 0.34 | 58 |
| Chub / Sunfish | Forest or Town river, morning | 0.33 | 60 |
| Eel | Beach, spring/fall rain, night | 0.33 | 60 |
| Catfish | Woods or river, rain | 0.33 | 61 |
| Walleye | Forest lake, fall/winter rain, afternoon+ | 0.30 | 66 |
| Shad | Town river, rain | 0.29 | 70 |
| Red Snapper | Beach, summer/fall/winter rain | 0.27 | 73 |
| Tilapia | Beach, summer/fall | 0.23 | 87 |
| Woodskip | Secret Woods | 0.23 | 88 |
| Bullhead / Largemouth Bass | Backwoods | 0.22 | 90 |
| Ghostfish | Mine floor 20 or 60 | 0.26 | 80 |
| Pufferfish | Beach, summer, sunny, 12:00-16:00 | 0.20 | 102 |
| Sturgeon | Backwoods or Mountain, summer/winter | 0.17 | 121 |
| Tiger Trout | Forest river, fall/winter | 0.16 | 129 |
| Tuna | Beach, summer/winter | 0.14 | 141 |

Insights: all bundle fish together need about 30 game hours if each is fished in its window. Fishing
level 2 vs 6 changes p only 5-20%. The constraint is the calendar window, not the time.

## 2. Quality Crops (`quality_crops.py`)
Plants needed for 95% chance of 5 gold: Farming 2 + Basic Fertilizer 76; Farming 4 + Basic 46;
Farming 5 + Quality Fertilizer 24; Farming 6 + Quality 21. Corn regrows every 4 days, so 10 plants give
about 80 rolls (about 15 gold at 19%). **Choose Corn + Pumpkin + Melon; skip Parsnip in Year 1.**
Farming XP per harvest: Pumpkin 30, Melon 27, Cauliflower 22, Corn 10, Parsnip 7.

## 3. Animals (`animals.py`): days after purchase to the first deluxe item (median / 95%)
Large Egg 15 / 18; Large Milk 15 / 18; L. Goat Milk 16 / 20; **Duck Feather 22 / 44; Rabbit's Foot 27 / 63**.
Chicken colour is 50/50 white or brown: buy 4 for 87.5% of having both. Goat not needed (Animal 5/6 is
covered by Large Milk, 2 Large Eggs, Duck Egg, Wool).

## 4. Luck sources (`luck_sources.py`)
Fruit bats: any 2 fruit kinds in a median 6 days; 2 Pomegranates 25 days; 3 Apples 69 days (90%: 139)
-> buy an Apple sapling (4,000g) by Summer 1 instead. Cart: 22% per season for a given item, 62% per year;
Red Cabbage (either cabbage or seeds) 86% over 32 visits.

## 5. Budget (`budget.py`)
Core Year 1 route: 95,250g + 1,748 wood + 699 stone (about 127,000g if all materials bought at Year 1
prices). Truffle via pig adds 45,000g + 1,000 wood. The same materials in Year 2 cost 157,300g instead
of 31,460g. Our bot's money peaked about 20,000g in Year 1: **income is the binding constraint.**

## 6. Income (`income.py`): profit per tile per season, base quality, planted day 1
Blueberry 524 (summer), Pumpkin 440 (fall), Grape 420 (fall, trellis), Corn 400 (summer through fall),
Cranberries 364, Melon 340, Potato 200 (best spring), Cauliflower 190. About 100 tiles of Blueberry in
summer and 100 of Pumpkin in fall cover the route; watering labour (sprinklers) is the real limit.

## Planner misses found in our run (fixable rules)
Maki Roll from Gus (300g, daily) bought in Y2 Winter; Earth Crystal and Quartz (floors 1-39) in Y2;
Ghostfish (floor 20, 26%/cast) in Y2 Winter; Pufferfish in Y2 Summer; Parsnip chased for Quality Crops.

## Next
Build the day-level simulator: route as a list of dated tasks, Monte Carlo over weather, luck, cart,
bats and animal rolls; output the completion-date distribution and the critical path.

## 7. World v1 + nightly planner: P(finish CC by Y1 Winter 28) (optimize1.py, compute/blockers.py)
Validated on 1,000 fresh seeds (95% Wilson CI).
- Bot speeds: best strategy P(Y1) 0.1% (0.0-0.6%); 26.1/31 bundles by Y1 end (baseline 24.3).
- Human speeds: best strategy P(Y1) 30.7% (27.9-33.6%); 29.0/31 bundles (baseline 0.7%, 27.4).
  Search seeds showed 42%: some overfitting, validation number is the honest one.
- Missing at Y1 end, human best: Dye 45% (Red Cabbage = cart luck), Chef's 22% (Truffle/Fried Egg),
  Field Research 12%, Animal 8%, Enchanter's 6%.
- Missing at Y1 end, bot best: Chef's 86%, Dye 71%, Enchanter's 65%, Animal 64%, Specialty Fish 53%, Fodder 33%.
- Value of single bot fixes (best human strategy at bot speeds, 300 seeds): fishing time per cast 20 -> 6 min
  is the only single fix that moves P(Y1) (0% -> 3.3%); better fish income 0.3%. Others ~0 alone.
  CAVEAT: 'overhead' and 'forage_tour_min' are not used by world1 (replaced by per-stop overheads, fixed
  20-min forage stops), so those two rows are invalid.
- Strategy must match speed: the best human strategy scores 0% at bot speeds (money-starved: 10k/25k Vault).

## 8. Objective v2: minimise CC completion time (optimize2.py, 100 search seeds, 1,000 validation seeds)
After fixing model holes (mine area revisits, Red Cabbage Y2, kitchen cooking, bus boarding, tapper ore):
- **Bot speeds:** best median **Y2 Fall 1 (day 168)**, p90 Y2 Winter 20. Baseline: median Y2 Winter 13 (day 208).
  Our real run (with daily Claude fixes) finished Y3 Summer 21 (day ~272).
  Best knobs: Vault first, reserve 200, 120 hand-watered tiles + 40 sprinkled, Potato/Blueberry/Pumpkin money
  crops, 45 Melons for Quality Crops, mine 2 days/week to floor 80, 6 chickens, 5 crab pots, pig for Truffle,
  fruit bats, build order Coop -> Big Coop -> Apple sapling -> Deluxe Coop -> Barn -> Pomegranate.
- **Human speeds:** best median **Y1 Winter 14 (day 97)**, p90 Y2 Summer 10.
  Best knobs: no Vault-first, 40 tiles + 40 sprinkled, Parsnip/Melon/Corn, pig AND kitchen, same build order.
- Both best plans agree on: Coop chain early (Coop -> Big Coop -> Apple -> Deluxe Coop) before the Barn,
  pig for Truffle, fruit bats, 6 chickens.
- SUSPECT: human-speed BASELINE shows median 'not done in 3 years' while bot baseline finishes Y2 Winter.
  Likely a model bug under human speeds with baseline knobs; check before trusting baseline comparisons.
