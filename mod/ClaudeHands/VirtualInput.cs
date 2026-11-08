using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using Microsoft.Xna.Framework.Input;
using StardewValley;

namespace ClaudeHands
{
    /// <summary>
    /// A virtual keyboard + mouse. Its state is merged into the game's raw device
    /// read (InputState.UpdateStates), so the game and SMAPI see it exactly like a
    /// physical device. Everything downstream (animations, stamina, time) is the
    /// game's own code path. This is the only way the agent affects the world.
    /// </summary>
    public static class VirtualInput
    {
        public static bool Enabled;               // set only while the save guard passes
        public static readonly HashSet<Keys> Held = new();
        private static readonly Dictionary<Keys, int> Taps = new(); // key -> ticks left
        public static bool MouseOverride;
        public static int MouseX, MouseY;
        public static bool MouseLeft, MouseRight;
        private static int mouseLeftTicks, mouseRightTicks;
        public static int ScrollValue;

        private static readonly AccessTools.FieldRef<InputState, KeyboardState> KbField =
            AccessTools.FieldRefAccess<InputState, KeyboardState>("_currentKeyboardState");
        private static readonly AccessTools.FieldRef<InputState, MouseState> MouseField =
            AccessTools.FieldRefAccess<InputState, MouseState>("_currentMouseState");

        public static void Patch(Harmony h)
        {
            h.Patch(AccessTools.Method(typeof(InputState), nameof(InputState.UpdateStates)),
                postfix: new HarmonyMethod(typeof(VirtualInput), nameof(AfterUpdateStates)));
            h.Patch(AccessTools.PropertyGetter(typeof(Game1), nameof(Game1.IsActiveNoOverlay)),
                postfix: new HarmonyMethod(typeof(VirtualInput), nameof(AfterIsActive)));
            // MonoGame's focus flag (GamePlatform.IsActive) gates input reading in Game1._update and
            // makes the game sleep when unfocused. Its getter is inlined, so hold the flag itself true.
            h.Patch(AccessTools.PropertySetter(PlatformType, "IsActive"),
                prefix: new HarmonyMethod(typeof(VirtualInput), nameof(BeforeSetActive)));
        }

        private static System.Type PlatformType => AccessTools.TypeByName("Microsoft.Xna.Framework.GamePlatform");
        private static object Platform => AccessTools.Field(typeof(Microsoft.Xna.Framework.Game), "Platform").GetValue(GameRunner.instance);

        private static void BeforeSetActive(ref bool value) { if (Enabled) value = true; }

        /// <summary>Call each tick: keep the window logically focused while the agent plays.</summary>
        public static void KeepActive()
        {
            if (Enabled && !GameRunner.instance.IsActive)
                AccessTools.PropertySetter(PlatformType, "IsActive").Invoke(Platform, new object[] { true });
        }

        public static void Tap(Keys k, int ticks = 3) => Taps[k] = ticks;

        public static void Click(int x, int y, bool right = false, int ticks = 3)
        {
            MouseOverride = true; MouseX = x; MouseY = y;
            if (right) mouseRightTicks = ticks; else mouseLeftTicks = ticks;
        }

        public static void ReleaseAll()
        {
            Held.Clear(); Taps.Clear();
            MouseLeft = MouseRight = false; mouseLeftTicks = mouseRightTicks = 0;
        }

        /// <summary>Called once per game tick to age taps.</summary>
        public static void Tick()
        {
            foreach (var k in Taps.Keys.ToList())
                if (--Taps[k] <= 0) Taps.Remove(k);
            if (mouseLeftTicks > 0) mouseLeftTicks--;
            if (mouseRightTicks > 0) mouseRightTicks--;
        }

        public static IEnumerable<Keys> Pressed => Held.Concat(Taps.Keys);

        private static void AfterUpdateStates(InputState __instance)
        {
            if (!Enabled) return;
            var real = KbField(__instance);
            var keys = real.GetPressedKeys().Concat(Pressed).Distinct().ToArray();
            KbField(__instance) = new KeyboardState(keys);
            if (MouseOverride)
            {
                var r = MouseField(__instance);
                bool l = MouseLeft || mouseLeftTicks > 0, rt = MouseRight || mouseRightTicks > 0;
                MouseField(__instance) = new MouseState(MouseX, MouseY, r.ScrollWheelValue + ScrollValue,
                    l ? ButtonState.Pressed : ButtonState.Released,
                    ButtonState.Released,
                    rt ? ButtonState.Pressed : ButtonState.Released,
                    ButtonState.Released, ButtonState.Released);
            }
        }

        // Window focus does not matter while the agent plays (it lives on another workspace).
        private static void AfterIsActive(ref bool __result)
        {
            if (Enabled) __result = true;
        }
    }
}
