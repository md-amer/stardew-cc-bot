using System;
using StardewValley;
using StardewValley.Menus;
using StardewValley.Tools;

namespace ClaudeHands
{
    /// <summary>
    /// Fishing with the mouse only: hold to charge the cast, click on nibble, then a
    /// 60 Hz controller holds/releases the button to keep the green bar on the fish.
    /// Reads only what the minigame shows on screen (fish and bar positions).
    /// </summary>
    public class FishTask
    {
        public string Status = "idle";
        public int Casts, Bites, Catches, Escapes;
        private int phase, wait, ticks, tx, ty, slot;
        private float lastDist;
        private float power = 0.97f;
        public bool Active => Status == "busy";

        public void Start(int x, int y, int slotIndex, float castPower = 0.97f) { power = castPower; tx = x; ty = y; slot = slotIndex; phase = 0; wait = 0; ticks = 0; Status = "busy"; }
        public void Stop(string why = "idle") { Status = why; VirtualInput.MouseLeft = false; }

        public void Tick()
        {
            if (!Active) return;
            var p = Game1.player;
            ticks++;
            if (wait > 0) { wait--; return; }
            var rod = p.CurrentTool as FishingRod;
            switch (phase)
            {
                case 0:
                    if (slot >= 0 && p.CurrentToolIndex != slot) { VirtualInput.Tap(ToolTask.SlotKeyPublic(slot), 2); wait = 5; }
                    phase = 1; break;
                case 1:
                    if (!StardewModdingAPI.Context.IsPlayerFree || p.UsingTool) { if (ticks > 600) Stop("failed:not_free"); return; }
                    if (rod == null) { Stop("failed:no_rod"); return; }
                    var (sx, sy) = ToolTask.TileToScreen(tx, ty);
                    VirtualInput.MouseOverride = true; VirtualInput.MouseX = sx; VirtualInput.MouseY = sy;
                    wait = 3; phase = 2; break;
                case 2: // charge cast
                    VirtualInput.MouseLeft = true; ticks = 0; phase = 3; break;
                case 3:
                    if (rod == null) { Stop("failed:no_rod"); return; }
                    if ((rod.isTimingCast && rod.castingPower >= power) || ticks > 150)
                    { VirtualInput.MouseLeft = false; Casts++; ticks = 0; phase = 4; }
                    break;
                case 4: // waiting for a bite (visible "!" over the bobber)
                    if (rod == null || (!rod.isFishing && !rod.isCasting && ticks > 120 && !p.UsingTool)) { Stop("done:no_cast"); return; }
                    if (rod.isNibbling) { VirtualInput.MouseLeft = true; wait = 3; phase = 5; ticks = 0; Bites++; }
                    else if (ticks > 60 * 60) { VirtualInput.MouseLeft = true; wait = 3; phase = 9; } // reel in empty after 60s
                    break;
                case 5:
                    VirtualInput.MouseLeft = false;
                    if (Game1.activeClickableMenu is BobberBar) { phase = 6; ticks = 0; }
                    else if (ticks > 120) { phase = 8; ticks = 0; } // missed, or junk/trash pulled straight out
                    break;
                case 6: // minigame
                    if (Game1.activeClickableMenu is not BobberBar bar) { VirtualInput.MouseLeft = false; if (lastDist > 0.9f) Catches++; else Escapes++; phase = 7; ticks = 0; return; }
                    lastDist = bar.distanceFromCatching;
                    Control(bar);
                    break;
                case 7: // result: catch shows fish held up -> click to continue
                    if (rod != null && (rod.fishCaught || rod.showingTreasure || rod.pullingOutOfWater))
                    {
                        if (ticks % 20 == 0) VirtualInput.Click(VirtualInput.MouseX, VirtualInput.MouseY, false, 3);
                        return;
                    }
                    if (Game1.activeClickableMenu is ItemGrabMenu) { Stop("done:treasure_menu"); return; }
                    if (!p.UsingTool && StardewModdingAPI.Context.IsPlayerFree) { if (ticks < 5) return; Stop("done"); }
                    else if (ticks > 900) Stop("failed:stuck_after");
                    break;
                case 8:
                    if (Game1.activeClickableMenu is BobberBar) { phase = 6; return; }
                    phase = 7; break;
                case 9:
                    VirtualInput.MouseLeft = false; phase = 7; ticks = 0; break;
            }
        }

        private void Control(BobberBar bar)
        {
            // bar top = bobberBarPos, height = bobberBarHeight; fish = bobberPosition (sprite ~28px)
            float barCenter = bar.bobberBarPos + bar.bobberBarHeight / 2f;
            float fish = bar.bobberPosition + 14f;
            // predict bar a few ticks ahead using its current speed (positive = falling)
            float predicted = barCenter + bar.bobberBarSpeed * 6f;
            VirtualInput.MouseLeft = predicted > fish;
            if (Math.Abs(predicted - fish) < 4 && Math.Abs(bar.bobberBarSpeed) < 0.5f) VirtualInput.MouseLeft = (Game1.ticks % 2) == 0;
        }
    }
}
