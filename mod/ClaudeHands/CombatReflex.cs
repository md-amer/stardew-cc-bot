using System.Linq;
using Microsoft.Xna.Framework;
using StardewValley;
using StardewValley.Locations;
using StardewValley.Monsters;
using StardewValley.Tools;

namespace ClaudeHands
{
    /// <summary>
    /// Player-like reflex in the mines: a monster within reach gets a weapon swing, through the same
    /// virtual mouse click a player uses (ToolTask). Runs every game update, so reaction time scales
    /// with fast-forward like every other system. Uses only what is on screen (monster positions).
    /// </summary>
    public static class CombatReflex
    {
        public static bool Enabled = true;
        public static int Swings;
        private static int cooldown;
        private const float Reach = 100f;   // px between centers (~1.5 tiles)

        public static void Tick(ToolTask tool, FishTask fish)
        {
            if (cooldown > 0) { cooldown--; return; }
            if (!Enabled || tool.Active || fish.Active) return;
            if (Game1.currentLocation is not MineShaft ms || !StardewModdingAPI.Context.IsPlayerFree) return;
            var p = Game1.player;
            if (p.UsingTool || Game1.activeClickableMenu != null) return;
            int slot = -1;
            for (int i = 0; i < 12 && i < p.Items.Count; i++)
                if (p.Items[i] is MeleeWeapon w && !w.isScythe()) { slot = i; break; }
            if (slot < 0) return;
            var me = p.GetBoundingBox().Center.ToVector2();
            var m = ms.characters.OfType<Monster>()
                .Where(x => !x.IsInvisible && x.Health > 0)
                .Select(x => (x, d: Vector2.Distance(me, x.GetBoundingBox().Center.ToVector2())))
                .Where(t => t.d < Reach).OrderBy(t => t.d).Select(t => t.x).FirstOrDefault();
            if (m == null) return;
            var c = m.GetBoundingBox().Center;
            tool.Start(c.X / 64, c.Y / 64, slot, false);
            tool.Reflex = true;
            Swings++;
            cooldown = 10;
        }
    }
}
