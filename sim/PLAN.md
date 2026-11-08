# Simulator plan (agreed 2026-11-08)

## Decisions (Amer)
- Objective (updated by Amer): **minimise Community Center completion time.** Year 1 is not required.
  Score = median completion day; 90th percentile reported (and used as tie-breaker).
- Sources: no preference given, so default = let the optimizer choose among Travelling Cart purchases,
  Desert trips (after Vault) and the pig for Truffle. Skull Cavern stays out of the main plan (combat is the
  bot's weakest skill); it is modelled later as an optional extra only.
- Speeds: plan for current bot speeds AND show what each execution fix would buy (human speeds as ceiling).
- Output: **a nightly day planner the bot runs** (live state + TV forecast -> tomorrow's task list).

## Known gaps in the current simulator (world.py v0)
1. One fixed greedy policy; the optimizer only tunes its knobs.
2. No time of day or travel: fish hours, shop hours (9-17, Gus 12+, bus 10-17), walking between maps.
3. Skill XP guessed; professions ignored; level gates (Fishing 3 crab pots, Farming 2 sprinklers, Farming 6
   cheese press) only roughly modelled.
4. Mining yields per floor invented; combat drops guessed.
5. Energy rough; no food.
6. TV forecast and daily luck (visible to players) unused.
7. Validation: only income matches our run.

## Work plan
A. Rules fixed (above).
B. Model v1:
   - 4 time slots per day (6-9, 9-12, 12-17, 17-2) with opening hours and fish hours per slot.
   - Travel matrix between locations from our walk logs (pos_trace.csv, 'long walk' events).
   - Every bundle source = an action with preconditions and effects taken from graph.py
     (so interactions come from data: reward -> machine -> item).
   - Skills: XP per action from code (fishing formula, foraging 7, crop formula, mining per stone type);
     professions at 5 and 10 (Tiller, Fisher, Miner, etc.).
   - Energy: tool costs from code, food optional.
   - Forecast: tomorrow's weather known each night (TV), luck known each morning.
C. Calibration: our single CC run was NOT optimal play (Amer). Use its data only for execution costs
   (minutes/energy per action) and game mechanics samples (yields, drop rates). Never as a strategy target.
   Mechanics come from decompiled code first; logs only check them. Replay of our run's choices is a
   mechanics sanity check (income ~137k Y1), not a goal.
D. Planners compared on the same seeds:
   1. knob policy + search (optimize.py),
   2. nightly rolling planner: score candidate task lists for tomorrow by progress on the critical path and
      deadline slack (items whose season or window closes soonest first), with money as a resource.
   The winner becomes the bot's planner (Python module the agent calls each night).
E. Experiments: bot vs human speeds; value of each fix (sprinklers, mining speed, overhead minutes);
   sensitivity of P(Year 1) to each assumption; cart / desert / pig on or off.
F. Output: `agent/` nightly planner + a readable Year 1 calendar of the typical plan with fallbacks.

## Done criteria
- Mechanics checks pass (fishing mix, income replay within ~20%); execution costs taken from logs.
- P(Year 1) reported with 95% interval over >= 200 seeds for bot speeds and for improved speeds.
- Planner runs in under 1 s per night inside the agent.
