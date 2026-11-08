using System.Linq;
using Microsoft.Xna.Framework.Input;
using StardewValley;

namespace ClaudeHands
{
    /// <summary>
    /// One tool swing / interaction at a tile, done the way a mouse player does it:
    /// select hotbar slot with its number key, put the cursor on the tile, click,
    /// wait for the animation to finish.
    /// </summary>
    public class ToolTask
    {
        public string Status = "idle"; // idle | busy | done | failed:<why>
        private int phase, wait, tx, ty, slot, ticks;
        private bool right;
        private string cancel;       // null | "water" | "hoe": cancel the animation once this effect is on the tile
        public int Cancels;
        private int after;
        public bool Active => Status == "busy";
        public bool Reflex;     // started by CombatReflex (not by an agent command)

        public void Start(int x, int y, int slotIndex, bool rightClick, string cancelOn = null)
        {
            tx = x; ty = y; slot = slotIndex; right = rightClick; phase = 0; wait = 0; ticks = 0; Status = "busy"; Reflex = false; cancel = cancelOn;
        }

        /// <summary>Has the tool's effect landed on the target tile?</summary>
        private bool EffectDone()
        {
            var loc = Game1.currentLocation;
            if (loc == null) return false;
            loc.terrainFeatures.TryGetValue(new Microsoft.Xna.Framework.Vector2(tx, ty), out var tf);
            var hd = tf as StardewValley.TerrainFeatures.HoeDirt;
            return cancel switch
            {
                "water" => hd != null && hd.state.Value == 1,
                "hoe" => hd != null,
                _ => false,
            };
        }

        public void Stop(string why = "idle") { Status = why; }

        public static Keys SlotKeyPublic(int i) => SlotKey(i);
        private static Keys SlotKey(int i)
        {
            var o = Game1.options;
            var arr = new[] { o.inventorySlot1, o.inventorySlot2, o.inventorySlot3, o.inventorySlot4, o.inventorySlot5, o.inventorySlot6,
                              o.inventorySlot7, o.inventorySlot8, o.inventorySlot9, o.inventorySlot10, o.inventorySlot11, o.inventorySlot12 };
            return arr[i].First().key;
        }

        /// <summary>Raw window pixel of a world tile's center.</summary>
        public static (int, int) TileToScreen(int x, int y)
        {
            float z = Game1.options.zoomLevel;
            return ((int)((x * 64 + 32 - Game1.viewport.X) * z), (int)((y * 64 + 32 - Game1.viewport.Y) * z));
        }

        public void Tick()
        {
            if (!Active) return;
            var p = Game1.player;
            if (++ticks > 600) { Stop("failed:timeout"); return; }
            if (wait > 0) { wait--; return; }
            switch (phase)
            {
                case 0: // select slot
                    if (slot >= 0 && slot < 12 && p.CurrentToolIndex != slot) { VirtualInput.Tap(SlotKey(slot), 2); wait = 4; }
                    phase = 1; break;
                case 1: // wait until player can act
                    if (!StardewModdingAPI.Context.IsPlayerFree || p.UsingTool) return;
                    if (slot >= 0 && slot < 12 && p.CurrentToolIndex != slot) { Stop("failed:slot"); return; }
                    var (sx, sy) = TileToScreen(tx, ty);
                    VirtualInput.MouseOverride = true; VirtualInput.MouseX = sx; VirtualInput.MouseY = sy;
                    wait = 3; phase = 2; break; // cursor moved -> becomes visible
                case 2:
                    { var (cx, cy) = TileToScreen(tx, ty); VirtualInput.Click(cx, cy, right, 3); }
                    wait = 4; phase = 3; break;
                case 3: // animation running
                    if (Game1.activeClickableMenu != null || Game1.eventUp) { Stop("done:menu"); return; }
                    // Animation cancel (wiki Tools § Bugs; decompiled Game1: RightShift+R+Delete while UsingTool
                    // -> completelyStopAnimatingOrDoingAction). Only after the effect is on the tile.
                    if (cancel != null && p.UsingTool && EffectDone())
                    {
                        VirtualInput.Tap(Keys.RightShift, 2); VirtualInput.Tap(Keys.R, 2); VirtualInput.Tap(Keys.Delete, 2);
                        Cancels++; wait = 3; phase = 4; return;
                    }
                    if (p.UsingTool || !p.CanMove) return;
                    Stop("done"); break;
                case 4: // after a cancel: the R of the combo is also a menu key in some bindings -> close that menu
                    if (Game1.activeClickableMenu is StardewValley.Menus.GameMenu gm) { gm.exitThisMenu(false); }
                    if (p.UsingTool) { if (ticks > 500) Stop("done"); return; }
                    if (++after < 3) return;           // give a late menu open the chance to appear and be closed
                    after = 0; Stop("done"); break;
            }
        }
    }
}
