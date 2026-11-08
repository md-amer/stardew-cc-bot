using System;
using System.Collections.Generic;
using System.Linq;
using Microsoft.Xna.Framework;
using StardewValley;
using StardewValley.Menus;
using StardewValley.TerrainFeatures;

namespace ClaudeHands
{
    /// <summary>
    /// Reads only information a player could see on screen or learn by normal play.
    /// Deliberately excluded: daily luck number, geode/treasure contents, mine ladder
    /// rolls, future weather beyond the TV forecast, hidden RNG.
    /// </summary>
    public static class StateReader
    {
        public static object Summary(Walker walker, ToolTask tool, FishTask fish)
        {
            var d = new Dictionary<string, object>
            {
                ["tick"] = Game1.ticks,
                ["title"] = Game1.activeClickableMenu is TitleMenu,
                ["world_ready"] = StardewModdingAPI.Context.IsWorldReady,
                ["menu"] = MenuInfo(),
                ["walker"] = walker.Status,
                ["keys"] = new { up = Game1.options.moveUpButton[0].key.ToString(), down = Game1.options.moveDownButton[0].key.ToString(), left = Game1.options.moveLeftButton[0].key.ToString(), right = Game1.options.moveRightButton[0].key.ToString(), menu = Game1.options.menuButton[0].key.ToString() },
                ["tool"] = tool.Status,
                ["fish"] = new { status = fish.Status, casts = fish.Casts, bites = fish.Bites, catches = fish.Catches, escapes = fish.Escapes },
                ["mouse"] = new { raw_x = Game1.getMouseXRaw(), raw_y = Game1.getMouseYRaw(), ui_x = Game1.getMouseX(true), ui_y = Game1.getMouseY(true), left = Game1.input.GetMouseState().LeftButton.ToString(), vo = VirtualInput.MouseOverride, active = GameRunner.instance.IsActive, no_overlay = Game1.game1.IsActiveNoOverlay, pad = Game1.options.gamepadControls, freeze = Game1.freezeControls, fade = Game1.globalFade, canmove = Game1.player?.CanMove, kb = string.Join(",", Game1.GetKeyboardState().GetPressedKeys()), last_press = ModEntry.LastPress, en = VirtualInput.Enabled, ui_scale = Game1.options.uiScale, zoom = Game1.options.zoomLevel },
            };
            if (!StardewModdingAPI.Context.IsWorldReady) return d;
            var p = Game1.player;
            d["time"] = Game1.timeOfDay;
            d["day"] = Game1.dayOfMonth;
            d["season"] = Game1.currentSeason;
            d["year"] = Game1.year;
            d["weather"] = Game1.isRaining ? (Game1.isLightning ? "storm" : "rain") : Game1.isSnowing ? "snow" : "sun";
            d["event"] = Game1.eventUp ? (Game1.CurrentEvent?.id ?? "?") : null;
            if (Game1.CurrentEvent is { skippable: true, skipped: false } ev)
            {
                // the on-screen skip button (same rectangle the game draws and hit-tests)
                var r = (Microsoft.Xna.Framework.Rectangle)HarmonyLib.AccessTools.Method(typeof(Event), "skipBounds").Invoke(ev, null);
                d["skip_button"] = new[] { r.Center.X, r.Center.Y };
            }
            d["held"] = Game1.player.CursorSlotItem?.Name ?? (Game1.activeClickableMenu is MenuWithInventory mwi ? mwi.heldItem?.Name : null);
            d["backpack"] = Game1.player.MaxItems;
            d["free"] = StardewModdingAPI.Context.IsPlayerFree;
            d["player"] = new Dictionary<string, object>
            {
                ["loc"] = Game1.currentLocation?.NameOrUniqueName,
                ["tile"] = new[] { p.TilePoint.X, p.TilePoint.Y },
                ["px"] = new[] { p.StandingPixel.X, p.StandingPixel.Y },
                ["facing"] = p.FacingDirection, // 0 up 1 right 2 down 3 left
                ["stamina"] = (int)p.Stamina, ["max_stamina"] = p.MaxStamina,
                ["health"] = p.health, ["max_health"] = p.maxHealth,
                ["money"] = p.Money,
                ["slot"] = p.CurrentToolIndex,
                ["item"] = p.CurrentItem?.Name,
                ["using_tool"] = p.UsingTool,
                ["moving"] = p.isMoving(),
                ["skills"] = new { farming = p.FarmingLevel, mining = p.MiningLevel, foraging = p.ForagingLevel, fishing = p.FishingLevel, combat = p.CombatLevel },
            };
            d["inventory"] = p.Items.Select((it, i) => it == null ? null : new { slot = i, name = it.Name, id = it.QualifiedItemId, stack = it.Stack, quality = (it as StardewValley.Object)?.Quality ?? 0, cat = it.Category, price = (it as StardewValley.Object)?.sellToStorePrice() ?? 0, edible = (it as StardewValley.Object)?.Edibility ?? -300, heal = (it as StardewValley.Object)?.Edibility > 0 ? (it as StardewValley.Object).healthRecoveredOnConsumption() : 0, water = (it as StardewValley.Tools.WateringCan)?.WaterLeft, water_max = (it as StardewValley.Tools.WateringCan)?.waterCanMax }).Where(x => x != null).ToList();
            return d;
        }

        public static object MenuInfo()
        {
            var m = Game1.activeClickableMenu;
            if (m == null) return null;
            var info = new Dictionary<string, object> { ["type"] = m.GetType().Name };
            if (m is DialogueBox db) info["text"] = db.getCurrentString();
            if (m is TitleMenu) info["sub"] = TitleMenu.subMenu?.GetType().Name;
            if (m is ItemGrabMenu igm && igm.ItemsToGrabMenu != null)
                info["grab"] = igm.ItemsToGrabMenu.actualInventory.Select((it, i) => it == null ? null : new { i, name = it.Name, stack = it.Stack, cat = it.Category }).Where(x => x != null).ToList();
            return info;
        }

        /// <summary>Objects, crops, features, NPCs, warps in the current location within radius r.</summary>
        public static object Around(int r)
        {
            var loc = Game1.currentLocation; var me = Game1.player.TilePoint;
            bool Near(Vector2 v) => Math.Abs(v.X - me.X) <= r && Math.Abs(v.Y - me.Y) <= r;
            var objects = loc.Objects.Pairs.Where(kv => Near(kv.Key))
                .Select(kv => new { x = (int)kv.Key.X, y = (int)kv.Key.Y, name = kv.Value.Name, id = kv.Value.QualifiedItemId, ready = kv.Value.readyForHarvest.Value, forage = kv.Value.isForage() && kv.Value.IsSpawnedObject, spawned = kv.Value.IsSpawnedObject, bc = kv.Value.bigCraftable.Value }).ToList();
            var features = loc.terrainFeatures.Pairs.Where(kv => Near(kv.Key)).Select(kv =>
            {
                var o = new Dictionary<string, object> { ["x"] = (int)kv.Key.X, ["y"] = (int)kv.Key.Y, ["type"] = kv.Value.GetType().Name };
                if (kv.Value is HoeDirt hd)
                {
                    o["watered"] = hd.state.Value == 1;
                    if (hd.crop != null)
                    {
                        o["crop"] = hd.crop.indexOfHarvest.Value;
                        o["ready"] = hd.readyForHarvest();
                        o["dead"] = hd.crop.dead.Value;
                    }
                }
                else if (kv.Value is Tree t) { o["stage"] = t.growthStage.Value; o["tree"] = t.treeType.Value; }
                else if (kv.Value is Grass) { }
                return o;
            }).ToList();
            var clumps = loc.resourceClumps.Where(c => Near(c.Tile)).Select(c => new { x = (int)c.Tile.X, y = (int)c.Tile.Y, w = c.width.Value, h = c.height.Value, id = c.parentSheetIndex.Value }).ToList();
            // festivals/events: villagers are event actors, not location characters (visible on screen either way)
            var chars = loc.characters.AsEnumerable();
            if (Game1.CurrentEvent?.actors != null) chars = chars.Concat(Game1.CurrentEvent.actors);
            var npcs = chars.Select(c => new { name = c.Name, x = c.TilePoint.X, y = c.TilePoint.Y, monster = c.IsMonster }).ToList();
            var debris = loc.debris.Where(x => x.item != null).Select(x => new { name = x.item.Name, x = (int)(x.Chunks.FirstOrDefault()?.position.X ?? 0) / 64, y = (int)(x.Chunks.FirstOrDefault()?.position.Y ?? 0) / 64 }).ToList();
            var warps = loc.warps.Select(w => new { x = w.X, y = w.Y, to = w.TargetName, tx = w.TargetX, ty = w.TargetY }).ToList();
            var doors = loc.doors.Pairs.Select(kv => new { x = kv.Key.X, y = kv.Key.Y, to = kv.Value }).ToList();
            // farm animals (visible: name tag, heart/pet bubble) and buildings with their door tiles
            var animals = loc.animals.Values.Select(a => new { name = a.Name, type = a.type.Value, x = a.TilePoint.X, y = a.TilePoint.Y, pet = a.wasPet.Value, adult = !a.isBaby(), friendship = a.friendshipTowardFarmer.Value }).ToList();
            var buildings = loc.buildings.Select(b => new { type = b.buildingType.Value, x = b.tileX.Value, y = b.tileY.Value, w = b.tilesWide.Value, h = b.tilesHigh.Value,
                door_x = b.tileX.Value + b.humanDoor.X, door_y = b.tileY.Value + b.humanDoor.Y, inside = b.GetIndoorsName(), building = b.isUnderConstruction(),
                adoor_x = b.tileX.Value + b.animalDoor.X, adoor_y = b.tileY.Value + b.animalDoor.Y, adoor_open = b.animalDoorOpen.Value, upgrading = b.daysUntilUpgrade.Value }).ToList();
            return new { loc = loc.NameOrUniqueName, w = loc.Map.Layers[0].LayerWidth, h = loc.Map.Layers[0].LayerHeight, objects, features, clumps, npcs, debris, warps, doors, animals, buildings };
        }

        /// <summary>Warp/door graph of all outdoor+indoor locations (public map knowledge).</summary>
        public static object WorldWarps()
        {
            var res = new System.Collections.Generic.Dictionary<string, object>();
            foreach (var loc in Game1.locations)
            {
                var warps = loc.warps.Select(w => new { x = w.X, y = w.Y, to = w.TargetName, tx = w.TargetX, ty = w.TargetY, door = false }).ToList();
                foreach (var kv in loc.doors.Pairs)
                {
                    // doors are action tiles; find the matching warp target via the map's Action property
                    var a = loc.doesTileHaveProperty(kv.Key.X, kv.Key.Y, "Action", "Buildings");
                    int tx = -1, ty = -1;
                    if (a != null)
                    {
                        var parts = a.Split(' ');
                        if (parts.Length >= 4 && (parts[0] == "Warp" || parts[0] == "LockedDoorWarp")) { int.TryParse(parts[1], out tx); int.TryParse(parts[2], out ty); }
                    }
                    warps.Add(new { x = kv.Key.X, y = kv.Key.Y, to = kv.Value, tx, ty, door = true });
                }
                res[loc.NameOrUniqueName] = warps;
            }
            return res;
        }

        /// <summary>Open shop: every item on sale with price/stock, plus scroll position (as shown in the shop UI).</summary>
        public static object Shop()
        {
            if (Game1.activeClickableMenu is not ShopMenu sm) return null;
            var items = sm.forSale.Select((it, i) =>
            {
                sm.itemPriceAndStock.TryGetValue(it, out var st);
                return new { i, name = it.DisplayName, id = (it as Item)?.QualifiedItemId, price = st?.Price ?? -1, stock = st?.Stock ?? -1 };
            }).ToList();
            var buttons = sm.forSaleButtons.Select(b => new { x = b.bounds.Center.X, y = b.bounds.Center.Y }).ToList();
            return new { top = sm.currentItemIndex, items, buttons, down = new { x = sm.downArrow.bounds.Center.X, y = sm.downArrow.bounds.Center.Y }, up = new { x = sm.upArrow.bounds.Center.X, y = sm.upArrow.bounds.Center.Y }, money = Game1.player.Money };
        }

        /// <summary>All tiles with an Action property in the current map (shop counters, doors, signs).</summary>
        public static object Actions()
        {
            var loc = Game1.currentLocation; var list = new List<object>();
            var layer = loc.Map.GetLayer("Buildings");
            for (int y = 0; y < layer.LayerHeight; y++)
                for (int x = 0; x < layer.LayerWidth; x++)
                {
                    var a = loc.doesTileHaveProperty(x, y, "Action", "Buildings");
                    if (a != null) list.Add(new { x, y, action = a });
                }
            return list;
        }

        /// <summary>Water tiles within r of the player (visible on screen).</summary>
        public static object Water(int r)
        {
            var loc = Game1.currentLocation; var me = Game1.player.TilePoint; var list = new List<int[]>();
            for (int y = me.Y - r; y <= me.Y + r; y++)
                for (int x = me.X - r; x <= me.X + r; x++)
                    if (loc.isTileOnMap(new Vector2(x, y)) && loc.isWaterTile(x, y) && loc.isOpenWater(x, y)) list.Add(new[] { x, y });
            return list;
        }

        /// <summary>Mine level info: ladders/shafts uncovered (visible tiles), monsters with health.</summary>
        public static object Mine()
        {
            if (Game1.currentLocation is not StardewValley.Locations.MineShaft ms) return null;
            var layer = ms.Map.GetLayer("Buildings");
            var ladders = new List<int[]>(); var shafts = new List<int[]>();
            for (int y = 0; y < layer.LayerHeight; y++)
                for (int x = 0; x < layer.LayerWidth; x++)
                {
                    var t = layer.Tiles[x, y];
                    if (t == null) continue;
                    if (t.TileIndex == 173) ladders.Add(new[] { x, y });
                    else if (t.TileIndex == 174) shafts.Add(new[] { x, y });
                }
            var monsters = ms.characters.OfType<StardewValley.Monsters.Monster>()
                .Select(m => new { name = m.Name, x = m.TilePoint.X, y = m.TilePoint.Y, hp = m.Health, px = m.StandingPixel.X, py = m.StandingPixel.Y }).ToList();
            var up = HarmonyLib.AccessTools.Field(typeof(StardewValley.Locations.MineShaft), "tileBeneathLadder")?.GetValue(ms);
            var elev = HarmonyLib.AccessTools.Field(typeof(StardewValley.Locations.MineShaft), "tileBeneathElevator")?.GetValue(ms);
            return new { level = ms.mineLevel, ladders, shafts, monsters, stones = ms.stonesLeftOnThisLevel, up_arrival = up?.ToString(), elevator_arrival = elev?.ToString() };
        }

        /// <summary>Walkability grid of the current location as rows of '.'/'#'.</summary>
        public static object Grid()
        {
            var loc = Game1.currentLocation;
            int w = loc.Map.Layers[0].LayerWidth, h = loc.Map.Layers[0].LayerHeight;
            var rows = new List<string>();
            for (int y = 0; y < h; y++)
            {
                var sb = new System.Text.StringBuilder(w);
                for (int x = 0; x < w; x++) sb.Append(Pathfinder.Walkable(loc, x, y) ? '.' : '#');
                rows.Add(sb.ToString());
            }
            return new { loc = loc.NameOrUniqueName, w, h, rows };
        }
    }
}
