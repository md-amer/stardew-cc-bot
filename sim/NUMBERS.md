# Planning numbers: sources and status

Every number for the planning simulator, with where it came from. Three source kinds:

- **[data]**: the game's own `Content/Data` files, dumped to `sim/data/game/*.json` by `sim/tools/datadump`
  (game v1.6.15, GOG). Read through `sim/gamedata.py`. These are exact.
- **[code]**: decompiled `Stardew Valley.dll` (`sim/decomp/`, ilspycmd). File named in each entry. Exact.
- **[run]**: measured from our own bot's 309 played days (`stats/`), read through `sim/empirical.py`.
  This is what OUR bot achieves, not the ideal.

`sim/decomp/` and `sim/data/game/` are game code/data: git-ignored, never publish.

Fair-play note: the bot never reads hidden RNG while playing (PROJECT.md rule). The planner uses the
formulas only for odds and averages, never to predict a specific seeded outcome.

## 1. Goal: bundles [data] `gamedata.bundles()`
30 Community Center bundles, 110 slots (115 with the Joja "Missing" bundle). Some bundles need only
part of their list: Quality Crops 3/4, Animal 5/6, Artisan 6/12, Exotic Foraging 5/9, Crab Pot 5/10,
Adventurer's 2/4. Full list: `python3 gamedata.py bundles`.

Forced chains found from the list:
- Enchanter's needs **Rabbit's Foot**, which comes from a rabbit, and a rabbit needs a **Deluxe Coop**
  (Coop 4000g, then Big Coop 10000g, then Deluxe Coop 20000g, then rabbit 4000g). So Wool (Animal) comes free.
  Other Rabbit's Foot sources are not yet checked.
- Dye needs **Duck Feather**, so a duck (needs Big Coop) is needed anyway; Duck Egg comes free.

## 2. Calendar and weather [data] Data/LocationContexts, [code] GameStateQuery.cs
- 4 seasons of 28 days. 1 game minute = 700 ms real at 1x (Game1.cs), so 10 min = 7 s and a full day
  6:00 to 2:00 = 14 real minutes.
- Festivals (shops closed, day mostly lost): Spring 13, Spring 24, Summer 11, Summer 28, Fall 16, Fall 27,
  Winter 8, Winter 25.
- Spring/Fall rain: 18.3% per day. A rain day becomes a storm 25% of the time once 28 days have been played.
- Summer rain: 12% + 0.3% x day of month (not on day 1). A summer rain day becomes a storm 85% of the time.
- Winter: snow 63%.
- Year 1 spring: days 1, 2, 3, 5 are always sunny, and day 4 always rains (exact day index to confirm).
- Rain waters crops; fish with weather "rainy" or "sunny" only bite in that weather.

## 3. Crops [data] Data/Crops + Data/Shops, [code] HoeDirt.cs, Crop.cs
- Per crop: phases, total grow days, regrow days, trellis, seasons, sell price, seed price
  (`python3 gamedata.py crops`).
- Seed prices (Pierre, Year 1): Parsnip 20, Bean 60, Cauliflower 80, Potato 50, Melon 80, Tomato 50,
  Blueberry 80, Hot Pepper 40, Wheat 10, Corn 150, Sunflower 200, Pumpkin 100, Eggplant 20, Yam 60.
  Garlic, Rice, Red Cabbage and Artichoke seeds are sold only from Year 2. **Red Cabbage (Dye bundle)
  therefore cannot come from Pierre in Year 1.** Other sources are not yet checked.
- Speed-Gro: total days x boost (0.10 Speed-Gro, 0.25 Deluxe, 0.33 Hyper; +0.10 Agriculturist;
  +0.25 paddy), rounded up, then removed one day at a time across phases, at most 3 passes (HoeDirt.cs:625).
- Gold-star chance: p = 0.2 x (farming level / 10) + 0.2 x fertilizer level x ((farming level + 2) / 12) + 0.01.
  Silver chance = min(0.75, 2p). Fertilizer level: Basic 1, Quality 2, Deluxe 3 (Crop.cs:565).
  Example: level 4 + Basic Fertilizer gives 19% gold.
- Basic Fertilizer and Speed-Gro: Pierre from day 15. Quality Fertilizer from Year 2, or craft at Farming 9.

## 4. Prices and shops [data] Data/Shops, [code] ShopBuilder.cs, Object.cs
- When the shop data says price -1, the price is 2 x the object price, except these year-based prices:
  Wood 10g (Y1) / 50g (Y2+), Stone 20 / 100, Coal 120 / 250 (in salePrice), Copper Ore 80 / 160,
  Iron Ore 150 / 250, Gold Ore 350 / 750 (Object.cs:7206).
- Clint's own list: Copper Ore 75, Iron Ore 150, Coal 150, Gold Ore 400 in Year 1; 150, 250, 250, 750 later.
- **Construction bundle (198 Wood + 99 Stone) costs about 4,000g at Robin in Year 1, and about 20,000g later.**
- Marnie: Hay 50, Milk Pail 1000, Shears 1000, Heater 2000.
- Fish shop: Crab Pot 1500 (Fishing 3), Bait 5 (Fishing 2), Deluxe Bait 100 (Fishing 4).

## 5. Buildings and animals [data] Data/Buildings, Data/FarmAnimals
- Coop 4000g + 300 wood + 100 stone (3 days). Big Coop 10000 + 400 + 150 (2 days).
  Deluxe Coop 20000 + 500 + 200 (2 days).
- Barn 6000 + 350 + 150 (3 days). Big Barn 12000 + 450 + 200. Deluxe Barn 25000 + 550 + 300.
- Silo 100 + 100 stone + 10 clay + 5 copper bars.
- Animals: chicken 400 (1 egg/day, adult after 3 days), duck 600 (every 2 days, 5 days; Big Coop),
  rabbit 4000 (every 4 days, 6 days; Deluxe Coop), cow 750 (daily, 5 days), goat 2000 (every 2 days, 5 days; Big Barn),
  sheep 4000 (every 3 days, 4 days; Deluxe Barn), pig 8000 (truffles, 10 days; Deluxe Barn).
- Large product needs friendship >= 200 (deluxe formula still to extract).

## 6. Machines [data] Data/Machines, Data/CraftingRecipes
- Unlocks: Mayonnaise Machine F2, Sprinkler F2, Bee House F3, Speed-Gro F3, Preserves Jar F4,
  Cheese Press F6, Loom F7, Keg F8, Oil Maker F8, Seed Maker F9; Crab Pot Fishing 3, Recycling Machine Fishing 4.
- Times: Cheese 200 min, Cloth 240 min, Jelly 4000 min (~3 days), Wine 10000 min (~7 days), Juice 6000,
  Truffle Oil 360, Honey 4 days, Mayo 180. Furnace: copper bar 30 min, iron 120, gold 300.
- Recycling Machine: Soggy Newspaper gives Cloth 10% of the time (Cloth without sheep or rabbit).

## 7. Skills and energy [code] Farmer.cs, Tools/*.cs
- XP to reach level: 100, 380, 770, 1300, 2150, 3300, 4800, 6900, 10000, 15000.
- Energy per use: Hoe 2 x power - 0.1 x farming level; Watering Can 2 x (power + 1) - 0.1 x farming level;
  Axe 2 x power - 0.1 x foraging level; Pickaxe 2 x (power + 1) - 0.1 x mining level;
  fishing cast 8 - 0.1 x fishing level.
- Farming XP per harvest: 16 x ln(0.018 x price + 1) (Crop.cs:692).

## 8. Fishing [data] Data/Fish + Data/Locations, [code] FishingRod.cs, GameLocation.cs:13901
- Bite wait: random between 600 and max(600, 30000 - 250 x fishing level) ms; x0.75 on first cast;
  bait x0.5 (Deluxe Bait a further x0.66); minimum 500 ms.
- Which fish: location list (plus Default) sorted by precedence then random; each entry rolls its chance,
  then the fish must pass time, weather and level checks. Fish weight = spawn - max(0, maxdepth - depth)
  x depthmult x spawn + fishing level / 50, capped at 0.9.
- **[run]** Our bot: median 20 game minutes per cast (1,033 timed casts). Top catches: Green Algae 161,
  Bullhead 152, Carp 152, Chub 143. The bite/escape counters in the log look cumulative, so the
  escape rate is not reliable yet.

## 9. Mining [code] MineShaft.cs:3614
- Ladder chance per stone: 0.02 + 1 / stones left + luck level / 100 + daily luck / 5, +0.04 with no
  monsters on the floor. The last stone always gives a ladder.
- Geode per stone: 0.022 x (1 + daily luck / 2 + mining level x 0.005 + luck level x 0.001);
  Frozen Geode from floor 40, Magma from floor 80.
- Omni Geode (floor 21 and below): 0.005 x the same factor.

## 10. Our bot's day [run] stats/day_summary.csv (309 days)
- Median 196 real seconds per game day at speed 8.
- Mean game minutes per day: fishing 149, farming 59, mining 57, community 64, chores 41, foraging 27,
  shopping 18, travel 6, sleep 7, **other 283** (unaccounted: waiting, menus, walking between steps).
- 1.96 failed steps per day. 2,996 long walks, median 50 tiles.

## 11. Crab pots [code] CrabPot.cs:360, [data] Data/Fish trap rows. `tables.crab_pot()`
- 20% junk (10% with Deluxe Bait). Otherwise the trap rows are tried in file order, each rolls its
  chance, first hit wins; no hit is junk.
- Per pot per day, ocean: Lobster 4.0%, Crab 7.6%, Oyster 10.3%, Clam 8.7%, Shrimp 9.9%, Cockle 11.9%,
  Mussel 9.7%, junk 38%. Freshwater: Snail 20%, Crayfish 21%, Periwinkle 21.5%, junk 37.6%.
- Clam, Cockle, Mussel and Oyster also spawn as Beach forage (see 12), so up to 4 of the 5 Crab Pot
  bundle slots can come without any crab pot.

## 12. Forage [code] GameLocation.cs:15136, [data] Data/Locations. `tables.forage()`
- Each location spawns U{min..max} items per day, capped at max on the map at once. Forest, Town,
  Mountain, Beach, BusStop: 1 to 4 a day, at most 6 at once. Each spawn picks an entry uniformly and keeps
  it with its Chance, so P(item) = chance / sum of chances that season.
- Examples (P per spawn): Forest spring Horseradish 50% / Dandelion 50%; Town spring Daffodil 100%;
  Mountain spring Leek 58%; Mountain fall Hazelnut 53%, Wild Plum 24%, Common Mushroom 24%;
  Beach winter Nautilus Shell 25%; Forest winter Crocus 39%, Crystal Fruit 39%.
- Winter Root and Snow Yam come from artifact spots in winter (Data/Locations Default ArtifactSpots).
- Flower Dance (Spring 24) Pierre sells Daffodil and Dandelion for 50g.

## 13. Travelling Cart [code] ItemQueryResolver.RANDOM_ITEMS, [data] Data/Shops Traveler
- Friday and Sunday. 10 objects drawn uniformly from a pool of 334 eligible objects, so any one item
  shows up 3.0% per visit, about 22% per season (8 visits).
- Price: max(random 100..1000 in steps of 100, base price x 3, 4 or 5).
- Of the bundle items, only these can NEVER come from the cart: Ancient Fruit, Aquamarine, Dinosaur
  Mayonnaise, Earth Crystal, Fire Quartz, Frozen Geode, Frozen Tear, Hay, Prismatic Shard, Quartz,
  Void Salmon. Everything else (Red Cabbage, Rabbit's Foot, Fried Egg, fruit...) can.

## 14. Other shops for bundle items [data] Data/Shops
- Saloon (Gus): **Maki Roll 300g, always in stock**, so no cooking is needed for it.
- Saloon dish of the day: uniform over 41 dishes, so Fried Egg 2.4% a day, about 50% per season.
- Fried Egg otherwise needs a kitchen: house upgrade 10,000g + 450 Wood (GameLocation.cs:12832).
- Sandy (Desert, needs the bus): Coconut 200 (Mon), Cactus Fruit 150 (Tue), Honey 200 (Fri).
- Krobus (Sewer): Void Essence 100, Solar Essence 80, Slime 10 (Mon), Bat Wing 30 (Sun).

## 15. Monsters [data] Data/Monsters (drop chance per kill)
- Green Slime: Slime 75% (+5%). Big Slime: Slime 99% (+90%, +40%).
- Bat: Bat Wing 90% (+40%); Frost Bat 90% (+55%); Lava Bat 90% (+70%).
- Solar Essence: Ghost 95%, Metal Head 65%, Squid Kid 75%, Mummy 99%.
- Void Essence: Shadow Brute/Shaman 75% (+10/20%), Serpent 99%.
- Dust Spirit: Frozen Tear 2%. Duggy: Earth Crystal 10%. Stone Golem: Quartz 10%.
- Rabbit's Foot: Serpent 0.8% (Skull Cavern only). Not a real option before the rabbit.

## 16. Mine minerals [code] MineShaft.cs:3878 and :3992, Utility.cs:6798
- Crystals lying on the floor: 25% the area mineral, else Quartz. Floors 1-39 Earth Crystal,
  40-79 Frozen Tear, 80-119 Fire Quartz.
- Gem nodes before reaching the mine bottom: floors under 40 only Amethyst or Topaz; Aquamarine nodes
  appear from floor 40.
- Geodes: half the time a mineral from a list of 12, otherwise a resource; the geode's bundle mineral
  comes out 6.25% of the time (Earth Crystal from Geode, Frozen Tear from Frozen Geode, Fire Quartz
  from Magma Geode). Omni Geode: 2.1% each.
- Recycling Machine: Soggy Newspaper gives Cloth 10%.

## 17. Animals in detail [code] FarmAnimal.cs:1029, :973
- Produce day: needs days since last >= DaysToProduce, then fullness/200 and happiness/70 rolls.
- Large/deluxe item: P = (happiness / 150, max 1) x [friendship >= minimum] x
  ((friendship + bonus) / divisor + daily luck x luck multiplier). Bonus = 1.5 x happiness when happiness > 200.
  Divisor 1200 for chicken, cow, goat; duck 4750; rabbit 5000 (no minimum friendship).
- Rabbit's Foot at full happiness: about 14% per produce at friendship 300, about 28% at 1000.
  A rabbit produces every 4 days.
- Friendship: +15 for petting each day; -(10 - friendship/200) on a day without petting; +8 for eating
  grass outside in good weather.

## 18. Luck, movement, XP [code] Game1.cs:7930, Farmer.cs, FishingRod.cs:1190
- Daily luck: uniform -0.100 to +0.100.
- Running: speed 5 x 0.066 px/ms = 0.33 px/ms, so about 5.2 tiles per real second at 1x, or about
  3.6 tiles per game minute. A 50-tile walk takes about 14 game minutes.
- Fishing XP: max(1, (quality + 1) x 3 + difficulty / 3), more for a perfect catch, x5 for a boss fish.
- Foraging XP 7 per item picked up. Mining XP per stone 1 to 5 by stone type.

## 19. Bundle and room rewards [data] Data/Bundles, [code] CommunityCenter.cs
Rewards hand out machines BEFORE their skill unlock, which changes the best order:
- Fall Crops: Bee House (normally Farming 3). Quality Crops: Preserves Jar (F4). Animal: Cheese Press (F6).
  Artisan: Keg (F8). Field Research: Recycling Machine (cloth from newspapers). Dye: Seed Maker.
- Vault 5,000g: 30 Quality Fertilizer, which raises the gold chance for Quality Crops
  (p = 0.2L/10 + 0.4(L+2)/12 + 0.01; at Farming 4: 29% vs 19% with Basic).
- Spring Crops: 20 Speed-Gro. River Fish: 30 Deluxe Bait. Geologist's: 5 Omni Geodes.
- Room rewards: Pantry = Greenhouse; Crafts Room = bridge to Quarry; Fish Tank = Glittering Boulder (panning);
  Boiler Room = minecarts; **Vault = bus to the Desert** (Sandfish, Coconut, Cactus Fruit, Sandy's shop,
  Skull Cavern). So the Vault must come before Specialty Fish and before Exotic Foraging via Sandy.

## 20. Farm cave [data] Data/Events/Farm key "65/m 25000/t 600 1200/H", [code] FarmCave.cs:216
- Demetrius event on entering the farm 6:00-12:00 after earning 25,000g total.
- Fruit bats: each day, items while random < 0.66, so on average 1.94 items a day, **in every season,
  winter included**. Each item: 1/5 each Salmonberry, Spice Berry, Wild Plum, Blackberry; 1/5 tree fruit
  (10% Apple, else Apricot/Orange/Peach/Pomegranate/Cherry evenly).
- Per day: Pomegranate 0.070, each of the other four fruits 0.070, Apple 0.039, Spice Berry 0.39.
  Expected days to the first Pomegranate about 14; 3 Apples (Fodder) about 77.
- Forum record holders choose bats for Year 1 CC (source: forums.stardewvalley.net threads).

## 21. More gift and drop sources
- NPC gift mail [code] Game1.cs:7915, [data] Data/mail: every night one random befriended NPC; chance =
  hearts x 10%; if picked, a random item from their list. Clint: Copper/Iron/Gold Bar. Emily: Sea Urchin, Cloth, Wool.
  Wizard: Purple Mushroom, Fire Quartz, Frozen Tear, Jade.
  Caroline: Potato, Cauliflower, Parsnip. Marnie: 30 Hay. Sandy: Coconut, Cactus Fruit. Linus: Maki Roll.
- Saloon dish of the day (Utility.IsForbiddenDishOfTheDay, Game1.UpdateDishOfTheDay): 41 dishes, uniform.
- Feast of the Winter Star shop: 2,500g random pick of Fire Quartz / Triple Shot / Powdermelon / ...,
  2,500g pick of Frozen Tear / Fried Mushroom / Duck Egg / Bread, 500g pick of Cave Carrot / Perch / Clam / Winter Root.
- Fishing treasure [code] FishingRod.cs:919: chest 15% per catch (+ daily luck / 2); first item certain,
  each extra 40%. A quarter of items roll the "mineral" branch where, at Fishing 2+, a third give
  minerals by cast distance: 4+ tiles 30% Fire Quartz; 3 tiles 30% Frozen Tear (else Jade or **Aquamarine**);
  under 3: 30% Earth Crystal. Another third give geodes (Frozen Geode possible at distance 4+).
  About 0.4% Fire Quartz per catch: a backup, not a plan.
- Mixed Seeds [code] Crop.cs:305: spring Parsnip 50% / Potato / Kale; summer Corn/Wheat/Hot Pepper/Radish;
  fall Corn/Eggplant/Artichoke/Pumpkin. **Never Red Cabbage.**

## 22. Red Cabbage in Year 1: all sources checked
- Pierre: YEAR 2. Night Market magic boat (Winter 15-17): also YEAR 2. Mixed Seeds: never.
- Red Cabbage Seeds drop 0.2% per Mummy or Serpent kill, and 0.5% from rare first-generation purple slimes,
  all Skull Cavern only (GreenSlime.cs:711, Mummy.cs:115, Serpent.cs:351).
- Travelling Cart: Red Cabbage and Red Cabbage Seeds are both eligible, about 6% per visit for either.
  Over roughly 30 Year 1 cart visits, about 84% to see one (seeds only help in summer or the greenhouse).
- So Year 1 Dye depends on luck at the cart, or a Year 1 Skull Cavern run.

## 23. Festivals [wiki] Festivals page
- Day festivals (Egg, Flower Dance, Luau, Fair, Ice): attend 9:00-14:00 (Fair to 15:00), then back on the
  farm at 22:00. All buildings stay locked all day even if skipped. Night festivals (Jellies, Spirit's
  Eve) leave the day free. Desert Festival (Spring 15-17), Trout Derby, SquidFest, Night Market: time runs, shops open.
- Visible info the bot may use: TV weather forecast for tomorrow, TV fortune (daily luck).

## 24. Validation of formulas against our 309 days [run]
- Weather seen: spring 14.7% rain (formula 18.3%, minus 4 forced-sun Y1 days), fall 17.2% (18.3%),
  winter 60% snow (63%), summer 25% wet (formula ~16% + 1 Green Rain day ~20%; within noise for n=80).

## 25. Our run's timeline: what came late [run] stats/events.jsonl "donated" lines
- End of Year 1: 16 bundles. Items that slipped to Year 2-3: Animal products (Large Milk, Large Egg,
  Goat Milk, Duck Egg end of Y1), Quality Parsnip (Y2 Sp6) and Melon (Y2 Su25), Red Cabbage (Y2 Sp26),
  Pufferfish (Y2 Su2), Wine (Y2 Su25), Aquamarine (Y2 Fa3), Earth Crystal (Y2 Fa14), 3 Apples (Y2 Fa24),
  Ghostfish (Y2 Wi2), Maki Roll (Y2 Wi4), Quartz + Fire Quartz (Y2 Wi10), Truffle (Y2 Wi28),
  Duck Feather (Y3 Sp19), Rabbit's Foot (Y3 Su21).
- Pure planning misses: Maki Roll (Gus sells it daily for 300g), Earth Crystal and Quartz (25%/75% of
  crystals on floors 1-39), Pufferfish (summer, 12:00-16:00 sunny, Beach). Big chains started late:
  coop upgrades and rabbit, barn and goat, keg (wine).

## 26. Outside reference: human speed routes
- Zamiell Min-Max guide (v1.6.0): fishing to level 10 by Spring 9, mine bottom (floor 120) by Spring
  14-18, 42,500g for the whole Vault by Spring 14, mostly via Kale. Ceiling for a perfect human player.
- speedrun.com Community Center Glitchless 1.6: about 2 h of real time (seed-dependent runs exist; they use
  RNG knowledge, which our fair-play rule forbids).

## Still open
Spawnable tile counts per map (do forage spawns ever fail?); exact Year 1 spring weather day index;
fishing minigame physics (BobberBar) for a catch-rate model; Queen of Sauce recipe schedule;
our bot's real escape rate (counter parsing).
