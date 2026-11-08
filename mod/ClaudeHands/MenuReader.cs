using System;
using System.Collections;
using System.Linq;
using System.Collections.Generic;
using System.Reflection;
using StardewValley;
using StardewValley.Menus;

namespace ClaudeHands
{
    /// <summary>Lists clickable widgets of the visible menu so the agent can click by name, like reading the screen.</summary>
    public static class MenuReader
    {
        public static IClickableMenu Top()
        {
            IClickableMenu m = Game1.activeClickableMenu;
            if (m is GameMenu gm) return gm.pages[gm.currentTab];
            if (m is TitleMenu && TitleMenu.subMenu != null) m = TitleMenu.subMenu;
            while (m?.GetChildMenu() != null) m = m.GetChildMenu();
            return m;
        }

        public static List<object> Widgets()
        {
            var list = new List<object>();
            var m = Top();
            if (m == null) return list;
            if (Game1.activeClickableMenu is GameMenu gm)
                for (int k = 0; k < gm.tabs.Count; k++) Add(list, "tabs", k, gm.tabs[k]);
            foreach (var f in m.GetType().GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
            {
                var v = f.GetValue(m);
                if (v is ClickableComponent cc) Add(list, f.Name, -1, cc);
                else if (v is InventoryMenu im)
                    for (int k = 0; k < im.inventory.Count; k++) Add(list, f.Name + ".slot", k, im.inventory[k]);
                else if (v is IEnumerable e && v is not string)
                {
                    int i = 0;
                    foreach (var x in e) { if (x is ClickableComponent c2) Add(list, f.Name, i, c2); i++; }
                }
            }
            return list;
        }

        /// <summary>Crafting page recipes as shown (name, can craft now, position).</summary>
        public static object Recipes()
        {
            if (Top() is not CraftingPage cp) return null;
            var page = cp.pagesOfCraftingRecipes[cp.currentCraftingPage];
            return page.Select(kv => new { name = kv.Value.name, can = kv.Value.doesFarmerHaveIngredientsInInventory(), x = kv.Key.bounds.Center.X, y = kv.Key.bounds.Center.Y }).ToList();
        }

        /// <summary>Junimo bundle note: bundles with completion and ingredients (as drawn on the note).</summary>
        public static object Bundles()
        {
            if (Game1.activeClickableMenu is not JunimoNoteMenu jm) return null;
            return new
            {
                specific = jm.specificBundlePage,
                current = jm.currentPageBundle?.name,
                bundles = jm.bundles.Select(b => new
                {
                    name = b.name, label = b.label, complete = b.complete, slots = b.numberOfIngredientSlots,
                    x = b.bounds.Center.X, y = b.bounds.Center.Y,
                    ingredients = b.ingredients.Select(ing => new
                    {
                        name = ing.id != null ? ItemRegistry.GetDataOrErrorItem(ing.id).DisplayName : null,
                        id = ing.id, stack = ing.stack, quality = ing.quality, done = ing.completed
                    }).ToList()
                }).ToList()
            };
        }

        /// <summary>
        /// Community Center progress without opening a menu: the same info the Junimo notes show
        /// (bundle names, done/missing ingredients) plus which rooms have a readable note.
        /// Room unlock rule (CommunityCenter.shouldNoteAppearInArea): Crafts Room always;
        /// Pantry + Fish Tank after 1 complete bundle; Boiler 2; Bulletin 3; Vault 4.
        /// </summary>
        public static object CommunityCenter()
        {
            var cc = Game1.getLocationFromName("CommunityCenter") as StardewValley.Locations.CommunityCenter;
            if (cc == null) return null;
            var flags = cc.bundlesDict();
            var list = new List<object>();
            foreach (var kv in Game1.netWorldState.Value.BundleData)
            {
                var key = kv.Key.Split('/');
                string room = key[0];
                int id = Convert.ToInt32(key[1]);
                var f = kv.Value.Split('/');
                var raw = ArgUtility.SplitBySpace(f[2]);
                int nItems = raw.Length / 3;
                int slots = f.Length > 4 && int.TryParse(f[4], out var s) && s > 0 ? s : nItems;
                flags.TryGetValue(id, out var done);
                var ings = new List<object>();
                for (int i = 0; i + 2 < raw.Length; i += 3)
                {
                    bool isMoney = int.TryParse(raw[i], out var n) && n < 0;
                    string name = isMoney ? "Gold" : ItemRegistry.GetDataOrErrorItem(raw[i]).DisplayName;
                    ings.Add(new { name, id = raw[i], stack = Convert.ToInt32(raw[i + 1]), quality = Convert.ToInt32(raw[i + 2]),
                                   done = done != null && i / 3 < done.Length && done[i / 3] });
                }
                int area = StardewValley.Locations.CommunityCenter.getAreaNumberFromName(room);
                list.Add(new { room, id, name = f[0], slots, complete = cc.isBundleComplete(id),
                               open = cc.shouldNoteAppearInArea(area), ingredients = ings });
            }
            return new { completeBundles = cc.numberOfCompleteBundles(), bundles = list };
        }

        private static void Add(List<object> list, string field, int i, ClickableComponent c)
        {
            if (!c.visible || c.bounds.Width == 0) return;
            list.Add(new { field, i, name = c.name, label = c.label, x = c.bounds.Center.X, y = c.bounds.Center.Y });
        }

        /// <summary>Robin's CarpenterMenu as drawn: current blueprint, buildable, placement mode.</summary>
        public static object Carpenter()
        {
            if (Game1.activeClickableMenu is not CarpenterMenu cm) return null;
            return new { id = cm.Blueprint?.Id, name = cm.Blueprint?.DisplayName, can = cm.CanBuildCurrentBlueprint(),
                         onFarm = cm.onFarm, freeze = cm.freeze, w = cm.Blueprint?.TilesWide, h = cm.Blueprint?.TilesHigh,
                         ok = new { x = cm.okButton.bounds.Center.X, y = cm.okButton.bounds.Center.Y },
                         fwd = new { x = cm.forwardButton.bounds.Center.X, y = cm.forwardButton.bounds.Center.Y },
                         cancel = new { x = cm.cancelButton.bounds.Center.X, y = cm.cancelButton.bounds.Center.Y } };
        }

        /// <summary>Visible top-left tiles where a w x h building fits (every tile buildable), with screen points.
        /// The screen point is the tile the game reads as the building's top-left (CarpenterMenu.tryToBuild).</summary>
        public static object BuildSpots(int w, int h, int cx, int cy)
        {
            var loc = Game1.currentLocation; var vp = Game1.viewport; var hits = new List<object>();
            int x0 = vp.X / 64 + 1, y0 = vp.Y / 64 + 1, x1 = (vp.X + vp.Width) / 64 - w - 1, y1 = (vp.Y + vp.Height) / 64 - h - 2;
            for (int y = y0; y <= y1; y++)
                for (int x = x0; x <= x1; x++)
                {
                    bool ok = true;
                    for (int dy = 0; dy < h + 1 && ok; dy++)          // + 1 row: free tile in front of the door
                        for (int dx = 0; dx < w && ok; dx++)
                            if (!loc.isBuildable(new Microsoft.Xna.Framework.Vector2(x + dx, y + dy))) ok = false;
                    if (!ok) continue;
                    float z = Game1.options.zoomLevel;
                    hits.Add(new { x, y, d = Math.Abs(x - cx) + Math.Abs(y - cy), sx = (int)((x * 64 + 32 - vp.X) * z), sy = (int)((y * 64 + 32 - vp.Y) * z) });
                }
            return hits.OrderBy(o => (int)o.GetType().GetProperty("d").GetValue(o)).Take(20).ToList();
        }

        /// <summary>Marnie's PurchaseAnimalsMenu: animal buttons, placement mode, naming box, animal houses on screen.</summary>
        public static object Animals()
        {
            if (Game1.activeClickableMenu is not PurchaseAnimalsMenu pm) return null;
            float z = Game1.options.zoomLevel; var vp = Game1.viewport;
            var houses = new List<object>();
            if (pm.onFarm)
                foreach (var b in Game1.getFarm().buildings)
                    if (b.GetIndoors() is AnimalHouse ah)
                        houses.Add(new { type = b.buildingType.Value, x = b.tileX.Value, y = b.tileY.Value, full = ah.isFull(), built = !b.isUnderConstruction(),
                                         sx = (int)(((b.tileX.Value + 1) * 64 + 32 - vp.X) * z), sy = (int)(((b.tileY.Value + 1) * 64 + 32 - vp.Y) * z) });
            return new { onFarm = pm.onFarm, naming = pm.namingAnimal, freeze = pm.freeze,
                         animals = pm.animalsToPurchase.Select(a => new { name = a.hoverText, avail = (a.item as StardewValley.Object)?.Type == null, price = a.item.salePrice(), x = a.bounds.Center.X, y = a.bounds.Center.Y }).ToList(),
                         done = new { x = pm.doneNamingButton.bounds.Center.X, y = pm.doneNamingButton.bounds.Center.Y },
                         ok = pm.okButton == null ? null : new { x = pm.okButton.bounds.Center.X, y = pm.okButton.bounds.Center.Y },
                         houses };
        }

        /// <summary>Whole-map spots for a w x h building (+ door row): tiles that are buildable now, or would be after
        /// clearing debris a player can remove (weeds, stones, twigs, grass, empty tilled soil). Fewest blockers first.</summary>
        public static object BuildPlan(int w, int h, int cx, int cy)
        {
            var loc = Game1.currentLocation; int W = loc.Map.Layers[0].LayerWidth, H = loc.Map.Layers[0].LayerHeight;
            var res = new List<(int x, int y, int n, int d, List<object> clear)>();
            for (int y = 1; y < H - h - 2; y++)
                for (int x = 1; x < W - w - 1; x++)
                {
                    bool ok = true; var clear = new List<object>();
                    for (int dy = 0; dy < h + 1 && ok; dy++)
                        for (int dx = 0; dx < w && ok; dx++)
                        {
                            var v = new Microsoft.Xna.Framework.Vector2(x + dx, y + dy);
                            if (loc.isBuildable(v)) continue;
                            if (loc.getBuildingAt(v) != null) { ok = false; break; }
                            bool mapOk = loc.doesTileHaveProperty(x + dx, y + dy, "Diggable", "Back") != null
                                         || loc.doesTileHavePropertyNoNull(x + dx, y + dy, "Buildable", "Back").ToLower().StartsWith("t");
                            if (!mapOk || loc.doesTileHaveProperty(x + dx, y + dy, "NoBuild", "Back") != null) { ok = false; break; }
                            string what = null;
                            if (loc.objects.TryGetValue(v, out var o))
                                what = (o.Name is "Weeds" or "Stone" or "Twig" || o.Name.Contains("Weeds")) ? o.Name : null;
                            else if (loc.terrainFeatures.TryGetValue(v, out var tf))
                                what = tf is StardewValley.TerrainFeatures.Grass ? "Grass"
                                     : (tf is StardewValley.TerrainFeatures.HoeDirt hd && hd.crop == null) ? "HoeDirt" : null;
                            if (what == null || loc.resourceClumps.Any(c => c.occupiesTile(x + dx, y + dy))) { ok = false; break; }
                            clear.Add(new { x = x + dx, y = y + dy, what });
                        }
                    if (ok) res.Add((x, y, clear.Count, Math.Abs(x - cx) + Math.Abs(y - cy), clear));
                }
            return res.OrderBy(r => r.n * 3 + r.d).Take(8).Select(r => new { r.x, r.y, blockers = r.n, r.d, r.clear }).ToList();
        }

        /// <summary>Screen point of a tile in the current viewport (null if off screen with margins).</summary>
        public static object TileScreen(int x, int y)
        {
            var vp = Game1.viewport; float z = Game1.options.zoomLevel;
            int px = x * 64 + 32 - vp.X, py = y * 64 + 32 - vp.Y;
            bool vis = px > 96 && py > 96 && px < vp.Width - 160 && py < vp.Height - 96;
            return new { sx = (int)(px * z), sy = (int)(py * z), visible = vis, sw = (int)(vp.Width * z), sh = (int)(vp.Height * z) };
        }
    }
}
