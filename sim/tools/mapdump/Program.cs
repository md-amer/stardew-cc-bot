using System; using System.IO; using System.Linq; using System.Collections.Generic; using Microsoft.Xna.Framework.Content; using Newtonsoft.Json;
class SP : IServiceProvider { public object GetService(Type t) => null; }
class P { static void Main(string[] a) {
  var cm = new ContentManager(new SP(), a[0]); var outDir = a[1]; Directory.CreateDirectory(outDir);
  foreach (var name in a.Skip(2)) {
    try {
      var map = cm.Load<xTile.Map>("Maps/" + name);
      var back = map.GetLayer("Back"); var bld = map.GetLayer("Buildings");
      int W = back.LayerWidth, H = back.LayerHeight;
      var grid = new System.Text.StringBuilder();
      for (int y = 0; y < H; y++) { for (int x = 0; x < W; x++) {
          var t = back.Tiles[x, y]; var b = bld?.Tiles[x, y];
          bool passable = t != null && (b == null || b.Properties.ContainsKey("Passable") || b.TileIndexProperties.ContainsKey("Passable"));
          if (t != null && (t.TileIndexProperties.ContainsKey("Water") || t.Properties.ContainsKey("Water"))) passable = false;
          if (t != null && (t.TileIndexProperties.TryGetValue("Passable", out var pv) && pv.ToString() == "F")) passable = false;
          grid.Append(passable ? '.' : '#'); }
        grid.Append('\n'); }
      var warps = new List<object>();
      if (map.Properties.TryGetValue("Warp", out var wv)) {
        var p = wv.ToString().Split(' ', StringSplitOptions.RemoveEmptyEntries);
        for (int i = 0; i + 4 < p.Length + 1 && i + 4 <= p.Length - 1 + 1; i += 5) if (i + 4 < p.Length) warps.Add(new { x = p[i], y = p[i+1], to = p[i+2], tx = p[i+3], ty = p[i+4], kind = "edge" });
      }
      if (bld != null) for (int y = 0; y < H; y++) for (int x = 0; x < W; x++) {
        var b = bld.Tiles[x, y]; if (b == null) continue;
        foreach (var props in new[]{ b.Properties, b.TileIndexProperties })
          if (props.TryGetValue("Action", out var av)) { var s = av.ToString();
            if (s.StartsWith("Warp") || s.StartsWith("LockedDoorWarp") || s.StartsWith("MagicWarp") || s.StartsWith("WarpCommunityCenter") || s.StartsWith("WarpWomensLocker") || s.StartsWith("WarpMensLocker"))
              warps.Add(new { x = x.ToString(), y = y.ToString(), action = s, kind = "door" }); }
      }
      File.WriteAllText(Path.Combine(outDir, name + ".json"), JsonConvert.SerializeObject(new { name, W, H, grid = grid.ToString(), warps }));
      Console.WriteLine($"ok {name} {W}x{H} warps {warps.Count}");
    } catch (Exception e) { Console.WriteLine($"FAIL {name}: {e.Message}"); }
  }
}}
