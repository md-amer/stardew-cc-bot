using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;
using StardewValley;

namespace ClaudeHands
{
    /// <summary>
    /// Runs a list of walk/use steps inside the game update loop, one after another, using the same
    /// Walker and ToolTask as single commands (same keys, same mouse clicks, same animations).
    /// Why: a Python round trip per tile wastes game time under fast-forward. Here the next step starts
    /// on the very next tick, so batch work (watering, planting) costs only its real animations.
    /// A failed walk skips the uses that follow it, up to the next walk.
    /// </summary>
    public class SeqTask
    {
        public string Status = "idle";   // idle | busy | done | done:menu | done:tired | stopped
        public int Done, Total, Skipped, Failed;
        private Queue<JObject> ops = new();
        private bool pendingWalk, skip;

        public bool Active => Status == "busy";

        public void Start(JArray list)
        {
            ops = new Queue<JObject>(list.Cast<JObject>());
            Total = ops.Count; Done = 0; Skipped = 0; Failed = 0; pendingWalk = false; skip = false;
            Status = Total > 0 ? "busy" : "done";
        }

        public void Stop(string why = "stopped") { ops.Clear(); Status = why; }

        public void Tick(Walker w, ToolTask t)
        {
            if (!Active || w.Active || t.Active) return;
            if (Game1.activeClickableMenu != null || Game1.eventUp) { Stop("done:menu"); return; }
            if (Game1.player.Stamina < 4) { Stop("done:tired"); return; }
            if (pendingWalk)
            {
                pendingWalk = false;
                skip = w.Status != "arrived";
                if (skip) Failed++;
            }
            if (ops.Count == 0) { Status = "done"; return; }
            var op = ops.Dequeue(); Done++;
            switch ((string)op["op"])
            {
                case "walk":
                    w.Start((int)op["x"], (int)op["y"], (bool?)op["adjacent"] ?? false);
                    pendingWalk = true;
                    break;
                case "use":
                    if (skip) { Skipped++; break; }
                    {   // empty watering can: stop so the agent refills (Fa 4: a failed refill walk wasted 40 swings)
                        int sl = (int?)op["slot"] ?? -1;
                        if ((string)op["cancel"] == "water" && sl >= 0 && sl < Game1.player.Items.Count
                            && Game1.player.Items[sl] is StardewValley.Tools.WateringCan can && can.WaterLeft <= 0)
                        { Stop("done:empty"); return; }
                    }
                    t.Start((int)op["x"], (int)op["y"], (int?)op["slot"] ?? -1, (bool?)op["right"] ?? false, (string)op["cancel"]);
                    break;
            }
        }
    }
}
