using System;
using System.Collections.Generic;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Input;
using StardewValley;

namespace ClaudeHands
{
    /// <summary>
    /// Walks the player to a tile by holding virtual movement keys along an A* path.
    /// Same speed and collisions as a human holding WASD.
    /// </summary>
    public class Walker
    {
        public string Status = "idle";      // idle | walking | arrived | failed:<why>
        private List<Point> path;
        private Point goal;
        private bool adjacent;
        private string locName;
        private int stuckTicks, replans, lastDist = int.MaxValue;
        private Vector2 lastPos;

        public bool Active => Status == "walking";

        public void Start(int x, int y, bool adjacentOk)
        {
            goal = new Point(x, y); adjacent = adjacentOk; replans = 0;
            locName = Game1.currentLocation?.NameOrUniqueName;
            Plan();
        }

        public void Stop(string why = "idle") { Status = why; path = null; ReleaseMove(); }

        private void Plan()
        {
            var loc = Game1.currentLocation; var st = Game1.player.TilePoint;
            path = Pathfinder.Find(loc, st, goal, adjacent);
            if (path == null && !Pathfinder.Walkable(loc, st.X, st.Y))
            {
                // standing inside a collider (bed, furniture edge): step to a free neighbour first
                foreach (var d in new[] { new Point(0, 1), new Point(1, 0), new Point(-1, 0), new Point(0, -1) })
                {
                    var n = new Point(st.X + d.X, st.Y + d.Y);
                    if (!Pathfinder.Walkable(loc, n.X, n.Y)) continue;
                    var rest = Pathfinder.Find(loc, n, goal, adjacent);
                    if (rest != null) { rest.Insert(0, n); path = rest; break; }
                }
            }
            stuckTicks = 0;
            if (path == null) Stop("failed:no_path"); else Status = "walking";
        }

        private static void ReleaseMove()
        {
            var o = Game1.options;
            foreach (var b in new[] { o.moveUpButton, o.moveDownButton, o.moveLeftButton, o.moveRightButton })
                VirtualInput.Held.Remove(b[0].key);
        }

        public void Tick()
        {
            if (!Active) return;
            if (Game1.currentLocation?.NameOrUniqueName != locName) { Stop("failed:location_changed"); return; }
            if (!Context()) { ReleaseMove(); return; } // menu/event: pause, resume after

            var p = Game1.player.StandingPixel;
            while (path.Count > 0)
            {
                var t = path[0];
                if (Math.Abs(p.X - (t.X * 64 + 32)) <= 10 && Math.Abs(p.Y - (t.Y * 64 + 32)) <= 10) path.RemoveAt(0);
                else break;
            }
            if (path.Count == 0) { Stop("arrived"); return; }

            var n = path[0];
            int dx = n.X * 64 + 32 - p.X, dy = n.Y * 64 + 32 - p.Y;
            ReleaseMove();
            var o = Game1.options;
            // Move along the dominant axis; correct the other axis only when far off-center.
            // Pressing both keys near corners snags on walls.
            bool horiz = Math.Abs(dx) >= Math.Abs(dy);
            if (horiz || Math.Abs(dx) > 24)
            {
                if (dx > 4) VirtualInput.Held.Add(o.moveRightButton[0].key);
                if (dx < -4) VirtualInput.Held.Add(o.moveLeftButton[0].key);
            }
            if (!horiz || Math.Abs(dy) > 24)
            {
                if (dy > 4) VirtualInput.Held.Add(o.moveDownButton[0].key);
                if (dy < -4) VirtualInput.Held.Add(o.moveUpButton[0].key);
            }

            // stuck detection: no movement for 45 ticks -> replan, 4 times -> fail
            if (Vector2.Distance(Game1.player.Position, lastPos) < 0.5f) stuckTicks++; else stuckTicks = 0;
            lastPos = Game1.player.Position;
            if (stuckTicks > 45)
            {
                if (++replans > 4) { Stop("failed:stuck"); return; }
                Plan();
            }
        }

        private static bool Context() =>
            StardewModdingAPI.Context.IsPlayerFree || Game1.player.isMoving();
    }

    public static class Pathfinder
    {
        public static bool Walkable(GameLocation loc, int x, int y)
        {
            if (!loc.isTileOnMap(new Vector2(x, y))) return false;
            var box = new Rectangle(x * 64 + 8, y * 64 + 16, 48, 32);
            return !loc.isCollidingPosition(box, Game1.viewport, true, 0, false, Game1.player, pathfinding: true);
        }

        public static List<Point> Find(GameLocation loc, Point start, Point goal, bool adjacent, int maxNodes = 40000)
        {
            bool IsGoal(Point q) => adjacent
                ? Math.Abs(q.X - goal.X) + Math.Abs(q.Y - goal.Y) == 1
                : q == goal;
            if (IsGoal(start)) return new List<Point>();
            var open = new PriorityQueue<Point, int>();
            var g = new Dictionary<Point, int> { [start] = 0 };
            var came = new Dictionary<Point, Point>();
            open.Enqueue(start, 0);
            int n = 0;
            var dirs = new[] { new Point(1, 0), new Point(-1, 0), new Point(0, 1), new Point(0, -1) };
            while (open.Count > 0 && n++ < maxNodes)
            {
                var c = open.Dequeue();
                if (IsGoal(c))
                {
                    var path = new List<Point> { c };
                    while (came.TryGetValue(c, out var prev) && prev != start) { path.Insert(0, prev); c = prev; }
                    return path;
                }
                foreach (var d in dirs)
                {
                    var nb = new Point(c.X + d.X, c.Y + d.Y);
                    if (!Walkable(loc, nb.X, nb.Y)) continue;
                    int ng = g[c] + 1;
                    if (g.TryGetValue(nb, out var old) && old <= ng) continue;
                    g[nb] = ng; came[nb] = c;
                    open.Enqueue(nb, ng + Math.Abs(nb.X - goal.X) + Math.Abs(nb.Y - goal.Y));
                }
            }
            return null;
        }
    }
}
