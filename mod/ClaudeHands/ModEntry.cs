using System.Collections.Generic;
using System;
using System.Collections.Concurrent;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using Microsoft.Xna.Framework.Input;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using StardewModdingAPI;
using StardewModdingAPI.Events;
using StardewValley;
using StardewValley.Menus;

namespace ClaudeHands
{
    public class ModEntry : Mod
    {
        /// <summary>The only farm the agent may touch. Everything else = inert.</summary>
        public const string AgentFarmer = "Claude";
        public const string AgentFarm = "Claude";
        public const int Port = 8775;
        public static string LastPress = "";

        private readonly ConcurrentQueue<(JObject cmd, TaskCompletionSource<string> tcs)> queue = new();
        private readonly Walker walker = new();
        private readonly ToolTask tool = new();
        private readonly FishTask fish = new();
        private readonly SeqTask seq = new();
        private HttpListener http;
        private bool foreignSaveLoaded;   // latched until game restart
        private StreamWriter actionLog;
        private DateTime lastCommand = DateTime.Now;
        public static bool AutoPause = true;

        public override void Entry(IModHelper helper)
        {
            var harmony = new Harmony(ModManifest.UniqueID);
            VirtualInput.Patch(harmony);
            Capture.Patch(harmony);
            FastForward.Patch(harmony);
            NoAchievements.Patch(harmony);
            FastForward.Gate = TurboWanted;
            helper.Events.GameLoop.UpdateTicked += OnTick;

            helper.Events.GameLoop.SaveLoaded += OnSaveLoaded;
            helper.Events.Input.ButtonPressed += (_, e) => LastPress = $"{e.Button}@{Game1.ticks}";
            helper.Events.GameLoop.ReturnedToTitle += (_, _) => { foreignSaveLoaded = false; walker.Stop(); VirtualInput.ReleaseAll(); };
            Directory.CreateDirectory(Path.Combine(helper.DirectoryPath, "logs"));
            actionLog = new StreamWriter(Path.Combine(helper.DirectoryPath, "logs", $"actions_{DateTime.Now:yyyyMMdd_HHmmss}.jsonl")) { AutoFlush = true };
            StartHttp();
        }

        // ---------------- save guard ----------------

        private void OnSaveLoaded(object s, SaveLoadedEventArgs e)
        {
            if (!IsAgentSave())
            {
                foreignSaveLoaded = true;
                VirtualInput.Enabled = false; VirtualInput.ReleaseAll(); walker.Stop();
                Monitor.Log($"Save '{Constants.SaveFolderName}' is not the agent's farm. ClaudeHands is inert until restart.", LogLevel.Warn);
            }
            else Game1.options.pauseWhenOutOfFocus = false; // vanilla option
        }

        private static bool IsAgentSave() =>
            Context.IsWorldReady
            && Game1.player.Name == AgentFarmer
            && Game1.player.farmName.Value == AgentFarm
            && (Constants.SaveFolderName?.StartsWith(AgentFarmer + "_") ?? false);

        /// <summary>Is the agent allowed to send input right now?</summary>
        private string GuardReason()
        {
            if (foreignSaveLoaded) return "foreign_save_loaded";
            if (Context.IsWorldReady) return IsAgentSave() ? null : "not_agent_save";
            // Title screen: allowed only for creating a new farm. Never the load menu.
            // Load and Co-op menus can open existing saves, so input is cut there.
            if (Game1.activeClickableMenu is TitleMenu)
                return TitleMenu.subMenu is null or CharacterCustomization ? null : "title_submenu_blocked:" + TitleMenu.subMenu.GetType().Name;
            if (Game1.activeClickableMenu is CharacterCustomization) return null;
            if (Game1.gameMode == Game1.loadingMode) return "loading";
            return null; // intro cutscene after new game
        }

        // ---------------- turbo gate ----------------
        private DateTime turboUntilReal = DateTime.MinValue;
        private int turboUntilClock = -1;

        private bool TurboWanted()
        {
            if (walker.Active || tool.Active || fish.Active || seq.Active) return true;
            if (!Context.IsWorldReady) return false;
            if (Game1.player.UsingTool || Game1.newDay || Game1.fadeToBlack || Game1.eventUp) return true;
            if (Game1.activeClickableMenu == null && !Context.IsPlayerFree) return true;   // warps, animations
            if (DateTime.Now < turboUntilReal)
            {
                if (turboUntilClock < 0 || Game1.timeOfDay < turboUntilClock) return true;
                turboUntilReal = DateTime.MinValue;
            }
            return false;
        }

        // ---------------- tick ----------------

        private void OnTick(object s, UpdateTickedEventArgs e)
        {
            var reason = GuardReason();
            VirtualInput.Enabled = reason == null;
            if (!VirtualInput.Enabled) { VirtualInput.ReleaseAll(); if (walker.Active) walker.Stop("failed:guard"); }

            // Dead-man switch: no agent command for 2 s and nothing running -> open the game menu
            // (single player: an open menu stops the clock, exactly like a player pausing to think).
            if (AutoPause && VirtualInput.Enabled && Context.IsWorldReady && Context.IsPlayerFree
                && !walker.Active && !tool.Active && !fish.Active && !seq.Active && Game1.activeClickableMenu == null
                && (DateTime.Now - lastCommand).TotalSeconds > 5 && !Game1.player.UsingTool)
            {
                VirtualInput.ReleaseAll();
                Game1.activeClickableMenu = new GameMenu();
            }
            int n = 0;
            while (n++ < 20 && queue.TryDequeue(out var item))
            {
                string res;
                // observers (stats dashboard) read only: they must not keep the dead-man switch from pausing
                if ((bool?)item.cmd["observer"] != true) lastCommand = DateTime.Now;
                try { res = Handle(item.cmd, reason); }
                catch (Exception ex) { res = JsonConvert.SerializeObject(new { ok = false, error = ex.Message }); }
                item.tcs.TrySetResult(res);
            }
            VirtualInput.KeepActive();
            if (VirtualInput.Enabled) { CombatReflex.Tick(tool, fish); walker.Tick(); tool.Tick(); fish.Tick(); seq.Tick(walker, tool); }
            VirtualInput.Tick();
        }

        private static Keys K(string name) => Enum.Parse<Keys>(name, true);

        private string Handle(JObject c, string guard)
        {
            string cmd = (string)c["cmd"];
            object Ok(object data = null) => new { ok = true, data };
            object result;
            bool input = cmd is not ("state" or "around" or "grid" or "ping" or "bundles" or "mine" or "recipes" or "water" or "actions" or "shop" or "world" or "widgets" or "screenshot" or "record" or "touch_tiles" or "tile_prop" or "diggable" or "carpenter" or "build_spots" or "animal_menu" or "build_plan" or "tile_screen" or "find_tile" or "cart" or "seq_status");
            if (input && guard != null) return JsonConvert.SerializeObject(new { ok = false, error = "guard:" + guard });
            if (input) actionLog.WriteLine(JsonConvert.SerializeObject(new { t = DateTime.Now.ToString("O"), gt = Context.IsWorldReady ? $"{Game1.currentSeason} {Game1.dayOfMonth} Y{Game1.year} {Game1.timeOfDay}" : "title", c }));

            switch (cmd)
            {
                case "screenshot": Capture.Pending.Enqueue((string)c["path"]); result = Ok(); break;
                case "record":
                    Capture.FrameDir = (string)c["dir"]; Capture.FrameEvery = (int?)c["every"] ?? 6; Capture.FrameScaleDiv = (int?)c["div"] ?? 2;
                    result = Ok(); break;
                case "ping": result = Ok(new { guard, observer = true, speed = FastForward.Speed }); break;
                case "autopause": AutoPause = (bool)c["on"]; result = Ok(); break;
                case "state": result = Ok(StateReader.Summary(walker, tool, fish)); break;
                case "around": result = Ok(StateReader.Around((int?)c["r"] ?? 12)); break;
                case "grid": result = Ok(StateReader.Grid()); break;
                case "bundles": result = Ok(MenuReader.Bundles()); break;
                case "cc": result = Ok(MenuReader.CommunityCenter()); break;
                case "reflex": if (c["on"] != null) CombatReflex.Enabled = (bool)c["on"]; result = Ok(new { on = CombatReflex.Enabled, swings = CombatReflex.Swings }); break;
                case "speed":
                    if (c["n"] != null) FastForward.Set((int)c["n"]);
                    if (c["headless"] != null) FastForward.Headless = (bool)c["headless"];
                    if (c["draw_every"] != null) FastForward.DrawEvery = Math.Max(1, (int)c["draw_every"]);
                    result = Ok(new { speed = FastForward.Speed, effective = Math.Round(FastForward.Effective, 1), gated = FastForward.Gated, turbo = Math.Round(FastForward.EffectiveTurbo > 1 ? FastForward.EffectiveTurbo : Math.Min(FastForward.Speed, 30), 1), headless = FastForward.Headless, draw_every = FastForward.DrawEvery });
                    break;
                case "turbo":   // let game time run fast while Python waits: for sec real seconds, or until clock >= until
                    turboUntilReal = DateTime.Now.AddSeconds(Math.Min(60.0, (double?)c["sec"] ?? 10));
                    turboUntilClock = (int?)c["until"] ?? -1;
                    result = Ok(new { until = turboUntilClock }); break;
                case "mine": result = Ok(StateReader.Mine()); break;
                case "recipes": result = Ok(MenuReader.Recipes()); break;
                case "carpenter": result = Ok(MenuReader.Carpenter()); break;
                case "build_spots": result = Ok(MenuReader.BuildSpots((int)c["w"], (int)c["h"], (int?)c["cx"] ?? 40, (int?)c["cy"] ?? 15)); break;
                case "animal_menu": result = Ok(MenuReader.Animals()); break;
                case "build_plan": result = Ok(MenuReader.BuildPlan((int)c["w"], (int)c["h"], (int?)c["cx"] ?? 50, (int?)c["cy"] ?? 15)); break;
                case "tile_screen": result = Ok(MenuReader.TileScreen((int)c["x"], (int)c["y"])); break;
                case "actions": result = Ok(StateReader.Actions()); break;
                case "shop": result = Ok(StateReader.Shop()); break;
                case "world": result = Ok(StateReader.WorldWarps()); break;
                case "hold":
                    foreach (var k in c["down"]?.Values<string>() ?? Enumerable.Empty<string>()) VirtualInput.Held.Add(K(k));
                    foreach (var k in c["up"]?.Values<string>() ?? Enumerable.Empty<string>()) VirtualInput.Held.Remove(K(k));
                    result = Ok(); break;
                case "tap": VirtualInput.Tap(K((string)c["key"]), (int?)c["ticks"] ?? 3); result = Ok(); break;
                case "click":
                {
                    // coords are UI pixels by default (menus); "world":true = zoomed world pixels relative to screen
                    float s = (bool?)c["world"] == true ? Game1.options.zoomLevel : Game1.options.uiScale;
                    VirtualInput.Click((int)((int)c["x"] * s), (int)((int)c["y"] * s), (bool?)c["right"] ?? false, (int?)c["ticks"] ?? 3);
                    result = Ok(); break;
                }
                case "widgets": result = Ok(new { menu = MenuReader.Top()?.GetType().Name, widgets = MenuReader.Widgets() }); break;
                case "type":
                    // same path as physical typing: SDL text input -> keyboard dispatcher -> focused text box
                    foreach (var ch in (string)c["text"]) Game1.keyboardDispatcher.Subscriber?.RecieveTextInput(ch);
                    result = Ok(); break;
                case "load_agent_save":
                {
                    // Loads ONLY the agent's own save (folder Claude_*). The load menu itself stays blocked.
                    if (Context.IsWorldReady || Game1.activeClickableMenu is not TitleMenu) { result = new { ok = false, error = "only from title screen" }; break; }
                    var dirs = Directory.GetDirectories(Constants.SavesPath, AgentFarmer + "_*").Select(Path.GetFileName).ToList();
                    if (dirs.Count != 1) { result = new { ok = false, error = "expected exactly one agent save, found " + dirs.Count }; break; }
                    SaveGame.Load(dirs[0]);
                    Game1.exitActiveMenu();
                    result = Ok(dirs[0]); break;
                }
                case "newgame_option":
                    // Only on the new-game screen; identical to ticking the box in Advanced Options.
                    if (Context.IsWorldReady) { result = new { ok = false, error = "only before game start" }; break; }
                    Game1.game1.SetNewGameOption((string)c["key"], (bool)c["value"]);
                    result = Ok(); break;
                case "mouse":
                    VirtualInput.MouseOverride = (bool?)c["override"] ?? true;
                    if (c["x"] != null) { VirtualInput.MouseX = (int)c["x"]; VirtualInput.MouseY = (int)c["y"]; }
                    if (c["left"] != null) VirtualInput.MouseLeft = (bool)c["left"];
                    if (c["right"] != null) VirtualInput.MouseRight = (bool)c["right"];
                    result = Ok(); break;
                case "release": VirtualInput.ReleaseAll(); walker.Stop(); tool.Stop(); result = Ok(); break;
                case "walk": walker.Start((int)c["x"], (int)c["y"], (bool?)c["adjacent"] ?? false); result = Ok(walker.Status); break;
                case "stop": walker.Stop(); tool.Stop(); fish.Stop(); seq.Stop(); result = Ok(); break;
                case "seq": seq.Start((JArray)c["ops"]); result = Ok(seq.Status); break;
                case "cart":
                    {
                        var f = Game1.getLocationFromName("Forest") as StardewValley.Locations.Forest;
                        var t = f?.GetTravelingMerchantCartTile();
                        result = Ok(new { x = t?.X, y = t?.Y, today = f?.ShouldTravelingMerchantVisitToday(), shop_x = t?.X + 4, shop_y = t?.Y + 1 });
                    }
                    break;
                case "find_tile":
                    {   // tiles in the current location whose tile index on a layer matches (e.g. bus ticket machine 1057)
                        var loc = Game1.currentLocation; var layer = loc.Map.GetLayer((string)c["layer"] ?? "Buildings");
                        int idx = (int)c["index"]; var hits = new List<object>();
                        for (int y = 0; y < layer.LayerHeight; y++)
                            for (int x = 0; x < layer.LayerWidth; x++)
                                if (layer.Tiles[x, y]?.TileIndex == idx) hits.Add(new { x, y });
                        result = Ok(hits);
                    }
                    break;
                case "touch_tiles":
                    {   // Back-layer TouchAction tiles in the current location (e.g. Desert "DesertBus" return bus)
                        var loc = Game1.currentLocation; var back = loc.Map.GetLayer("Back"); var hits = new List<object>();
                        for (int y = 0; y < back.LayerHeight; y++)
                            for (int x = 0; x < back.LayerWidth; x++)
                            {
                                string ta = loc.doesTileHaveProperty(x, y, "TouchAction", "Back");
                                if (ta != null) hits.Add(new { x, y, action = ta });
                            }
                        result = Ok(hits);
                    }
                    break;
                case "tile_prop":
                    {   // tiles with a map property (e.g. "Trough" on Back = feeding bench in animal houses)
                        var loc = Game1.currentLocation; string layer = (string)c["layer"] ?? "Back", prop = (string)c["prop"];
                        var L = loc.Map.GetLayer(layer); var hits = new List<object>();
                        for (int y = 0; y < L.LayerHeight; y++)
                            for (int x = 0; x < L.LayerWidth; x++)
                                if (loc.doesTileHaveProperty(x, y, prop, layer) != null)
                                    hits.Add(new { x, y, has_obj = loc.objects.ContainsKey(new Microsoft.Xna.Framework.Vector2(x, y)) });
                        result = Ok(hits);
                    }
                    break;
                case "diggable":
                    {   // free tillable tiles near the farmer (winter: 4% Winter Root per tilled tile off-farm, wiki Winter Root)
                        var loc = Game1.currentLocation; int r = (int?)c["r"] ?? 12; var me = Game1.player.TilePoint; var hits = new List<object>();
                        for (int y = me.Y - r; y <= me.Y + r; y++)
                            for (int x = me.X - r; x <= me.X + r; x++)
                            {
                                var v = new Microsoft.Xna.Framework.Vector2(x, y);
                                if (!loc.isTileOnMap(v) || loc.doesTileHaveProperty(x, y, "Diggable", "Back") == null) continue;
                                if (loc.objects.ContainsKey(v) || loc.terrainFeatures.ContainsKey(v) || !loc.isTilePassable(new xTile.Dimensions.Location(x, y), Game1.viewport)) continue;
                                if (loc.isCollidingPosition(new Microsoft.Xna.Framework.Rectangle(x * 64 + 2, y * 64 + 2, 60, 60), Game1.viewport, true, 0, false, Game1.player)) continue;
                                hits.Add(new { x, y });
                            }
                        result = Ok(hits);
                    }
                    break;
                case "seq_status": result = Ok(new { status = seq.Status, done = seq.Done, total = seq.Total, skipped = seq.Skipped, failed = seq.Failed }); break;
                case "fish": fish.Start((int)c["x"], (int)c["y"], (int?)c["slot"] ?? -1, (float?)c["power"] ?? 0.97f); result = Ok(); break;
                case "water": result = Ok(StateReader.Water((int?)c["r"] ?? 8)); break;
                case "use": tool.Start((int)c["x"], (int)c["y"], (int?)c["slot"] ?? -1, (bool?)c["right"] ?? false, (string)c["cancel"]); result = Ok(); break;
                default: result = new { ok = false, error = "unknown cmd " + cmd }; break;
            }
            return JsonConvert.SerializeObject(result);
        }

        // ---------------- http ----------------

        private void StartHttp()
        {
            http = new HttpListener();
            http.Prefixes.Add($"http://127.0.0.1:{Port}/");
            http.Start();
            new Thread(() =>
            {
                while (http.IsListening)
                {
                    HttpListenerContext ctx;
                    try { ctx = http.GetContext(); } catch { break; }
                    ThreadPool.QueueUserWorkItem(_ => Serve(ctx));
                }
            }) { IsBackground = true, Name = "ClaudeHands-http" }.Start();
            Monitor.Log($"Listening on 127.0.0.1:{Port}", LogLevel.Info);
        }

        private void Serve(HttpListenerContext ctx)
        {
            string body;
            try { using var r = new StreamReader(ctx.Request.InputStream); body = r.ReadToEnd(); }
            catch { return; }
            string res;
            try
            {
                var cmd = string.IsNullOrWhiteSpace(body) ? new JObject { ["cmd"] = ctx.Request.Url.AbsolutePath.Trim('/') } : JObject.Parse(body);
                var tcs = new TaskCompletionSource<string>();
                queue.Enqueue((cmd, tcs));
                res = tcs.Task.Wait(10000) ? tcs.Task.Result : "{\"ok\":false,\"error\":\"timeout (game paused?)\"}";
            }
            catch (Exception ex) { res = JsonConvert.SerializeObject(new { ok = false, error = ex.Message }); }
            // client may have gone away (killed script): never let that crash the game
            try
            {
                var bytes = Encoding.UTF8.GetBytes(res);
                ctx.Response.ContentType = "application/json";
                ctx.Response.OutputStream.Write(bytes, 0, bytes.Length);
                ctx.Response.Close();
            }
            catch (Exception ex) { Monitor.Log("http write failed: " + ex.Message, LogLevel.Trace); }
        }
    }
}
