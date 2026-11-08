using System;
using System.Collections.Concurrent;
using System.IO;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using StardewValley;

namespace ClaudeHands
{
    /// <summary>
    /// Grabs the game's own back buffer right after it draws, so screenshots work
    /// even when the window is on a hidden workspace. Also supports a periodic
    /// frame dump for timelapse videos.
    /// </summary>
    public static class Capture
    {
        public static readonly ConcurrentQueue<string> Pending = new();
        public static string FrameDir;      // non-null = record frames
        public static int FrameEvery = 6;   // every Nth rendered frame
        public static int FrameScaleDiv = 2;
        private static int frameCount, frameIndex;

        /// <summary>Hook GraphicsDevice.Present so captures include menus/HUD (drawn after SMAPI's Rendered event).</summary>
        public static void Patch(HarmonyLib.Harmony h)
        {
            h.Patch(HarmonyLib.AccessTools.Method(typeof(GraphicsDevice), "Present", System.Type.EmptyTypes),
                prefix: new HarmonyLib.HarmonyMethod(typeof(Capture), nameof(OnRendered)));
        }

        public static void OnRendered()
        {
            if (Pending.TryDequeue(out var path)) Save(path, 1);
            if (FrameDir != null && ++frameCount % FrameEvery == 0)
                Save(Path.Combine(FrameDir, $"f{frameIndex++:D7}.png"), FrameScaleDiv);
        }

        private static void Save(string path, int div)
        {
            try
            {
                var gd = Game1.graphics.GraphicsDevice;
                int w = gd.PresentationParameters.BackBufferWidth, h = gd.PresentationParameters.BackBufferHeight;
                var data = new Color[w * h];
                gd.GetBackBufferData(data);
                int ow = w / div, oh = h / div;
                var outData = new Color[ow * oh];
                // back buffer read at Present is top-down
                for (int y = 0; y < oh; y++)
                    for (int x = 0; x < ow; x++) outData[y * ow + x] = data[(y * div) * w + x * div];
                for (int i = 0; i < outData.Length; i++) outData[i].A = 255;
                using var tex = new Texture2D(gd, ow, oh);
                tex.SetData(outData);
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                using var fs = File.Create(path);
                tex.SaveAsPng(fs, ow, oh);
            }
            catch (Exception ex) { File.WriteAllText(path + ".err", ex.ToString()); }
        }
    }
}
