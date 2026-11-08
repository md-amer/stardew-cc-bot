using HarmonyLib;
using StardewValley;

namespace ClaudeHands
{
    /// <summary>Bot-made progress must never unlock Steam/GOG achievements: skip the platform unlock call.
    /// The in-game achievement list still updates (local save only).</summary>
    internal static class NoAchievements
    {
        public static void Patch(Harmony h)
        {
            h.Patch(AccessTools.Method(typeof(Game1), nameof(Game1.getPlatformAchievement)),
                prefix: new HarmonyMethod(typeof(NoAchievements), nameof(Skip)));
        }

        private static bool Skip() => false;
    }
}
