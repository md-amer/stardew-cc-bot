using System;
using System.Diagnostics;
using System.Reflection;
using HarmonyLib;
using Microsoft.Xna.Framework;

namespace ClaudeHands
{
    /// <summary>
    /// Fair fast-forward: runs the WHOLE game update N times per rendered frame.
    /// Every system advances together (clock, movement, NPCs, crops, monsters, fishing bar,
    /// SMAPI events, and this mod's own walker/fishing controllers), so difficulty is unchanged.
    /// This is not a clock-stretch: nothing gets more done per game minute than at 1x.
    /// Hook: SMAPI's SGameRunner.Update (one full SMAPI+game tick, including input and events).
    ///
    /// Headless turbo (session 5, Amer: "I don't need to see the game, but save videos"): drawing is skipped
    /// except one frame every <see cref="DrawEvery"/> game updates, so the time goes to updates instead of
    /// rendering. Extra updates per frame are limited by a time budget, not a fixed count. The drawn frames
    /// keep an even game-time spacing, so the frame dump still makes a smooth timelapse.
    /// </summary>
    public static class FastForward
    {
        public static int Speed = 1;          // updates per frame; 1 = vanilla
        public const int MaxSpeed = 200;
        public static bool Headless;          // skip drawing between timelapse frames
        public static int DrawEvery = 60;     // game updates per drawn frame in headless mode (60 = 1 game second)
        public static double BudgetMs = 14;   // wall-clock budget for extra updates per frame
        public static double Effective = 1;   // measured game updates per real 1/60 s
        public static double EffectiveTurbo = 1;  // same, measured only over windows that ran mostly gated
        private static int framesWin, gatedWin;
        // LESSONS 120: turbo only while the game, not Python, is in control (a mod task runs, a transition/event
        // plays, or Python asked for a time skip). Otherwise 1 update per frame, so Python round trips cost
        // game seconds, not game hours.
        public static Func<bool> Gate = () => true;
        public static bool Gated => Speed > 1 && Gate();
        private static bool inner;
        private static MethodInfo update;
        private static int sinceDraw, countWin;
        private static readonly Stopwatch win = Stopwatch.StartNew();

        public static void Patch(Harmony h)
        {
            var t = AccessTools.TypeByName("StardewModdingAPI.Framework.SGameRunner");
            update = AccessTools.Method(t, "Update", new[] { typeof(GameTime) });
            h.Patch(update, prefix: new HarmonyMethod(typeof(FastForward), nameof(Before)));
            var bd = AccessTools.DeclaredMethod(typeof(Game), "BeginDraw");
            h.Patch(bd, prefix: new HarmonyMethod(typeof(FastForward), nameof(BeforeDraw)));
        }

        public static void Set(int n) => Speed = Math.Clamp(n, 1, MaxSpeed);

        private static void Before(object __instance, GameTime gameTime)
        {
            if (inner) return;
            int n = 1;
            framesWin++;
            if (Gated)
            {
                gatedWin++;
                inner = true;
                var sw = Stopwatch.StartNew();
                try
                {
                    for (int i = 1; i < Speed; i++)
                    {
                        if (sw.Elapsed.TotalMilliseconds > BudgetMs) break;
                        update.Invoke(__instance, new object[] { gameTime });   // re-enters this prefix with inner=true
                        n++;
                    }
                }
                finally { inner = false; }
            }
            sinceDraw += n; countWin += n;
            if (win.ElapsedMilliseconds >= 1000)
            {
                Effective = countWin / (win.Elapsed.TotalSeconds * 60.0);
                if (gatedWin * 2 > framesWin) EffectiveTurbo = Effective;
                countWin = 0; framesWin = 0; gatedWin = 0; win.Restart();
            }
        }

        /// <summary>MonoGame skips Draw and Present when BeginDraw returns false.</summary>
        private static bool BeforeDraw(ref bool __result)
        {
            if (!Headless || !Gated || Capture.Pending.Count > 0) { sinceDraw = 0; return true; }
            if (sinceDraw >= DrawEvery) { sinceDraw = 0; return true; }
            __result = false;
            return false;
        }
    }
}
