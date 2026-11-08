"""Claude Plays Stardew: live stats dashboard (Textual). Run: scripts/stats.sh"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich import box
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, Footer, Sparkline
import data

GOLD, GREEN, RED, BLUE, PINK, PURPLE, CYAN, ORANGE = "#ffd60a", "#80ed99", "#ff595e", "#3a86ff", "#ff70a6", "#c77dff", "#4cc9f0", "#f77f00"
SEASON_COL = {"spring": GREEN, "summer": GOLD, "fall": ORANGE, "winter": CYAN}
WEATHER_ICON = {"sun": "☀", "rain": "☂", "storm": "⚡", "snow": "❄", "wind": "🍃"}
ROOMS = ["Crafts Room", "Pantry", "Fish Tank", "Boiler Room", "Bulletin Board", "Vault"]
SKILLS = [("farming", GREEN), ("mining", ORANGE), ("foraging", PURPLE), ("fishing", CYAN), ("combat", RED)]


def bar(v, mx, width, col, empty="#2b2d42"):
    v = max(0, min(v or 0, mx or 1)); n = int(round(width * v / (mx or 1)))
    return Text("█" * n, style=col) + Text("█" * (width - n), style=empty)


def clock(t):
    if t is None: return "--:--"
    h, m = divmod(t, 100); h %= 24
    return f"{(h % 12) or 12}:{m:02d} {'am' if h < 12 else 'pm'}"


class Card(Static):
    pass


class StatsApp(App):
    TITLE = "Claude Plays Stardew"
    CSS = """
    Screen { background: #0d1021; }
    #banner { height: 3; content-align: center middle; background: #1b1e3c; color: #ffd60a; text-style: bold; }
    #cards { height: 5; }
    Card { width: 1fr; border: round #3a3f73; padding: 0 1; background: #14172e; }
    #mid { height: 14; }
    #money_box { width: 2fr; border: round #ffd60a; background: #14172e; padding: 0 1; }
    #money_title { height: 1; color: #ffd60a; text-style: bold; }
    Sparkline { height: 1fr; }
    Sparkline > .sparkline--max-color { color: #ffd60a; }
    Sparkline > .sparkline--min-color { color: #ff70a6; }
    #skills { width: 1fr; height: 100%; border: round #80ed99; background: #14172e; padding: 0 1; }
    #cc { width: 1fr; height: 100%; border: round #c77dff; background: #14172e; padding: 0 1; }
    #low { height: 1fr; }
    #activity { width: 1fr; height: 100%; border: round #4cc9f0; background: #14172e; padding: 0 1; }
    #loot { width: 1fr; height: 100%; border: round #ff70a6; background: #14172e; padding: 0 1; }
    #feed { width: 1fr; border: round #3a86ff; background: #14172e; padding: 0 1; }
    """
    BINDINGS = [("q", "quit", "Quit"), ("r", "refresh", "Refresh now"), ("t", "toggle_scope", "Today / All-time")]

    def compose(self) -> ComposeResult:
        yield Static(id="banner")
        with Horizontal(id="cards"):
            for i in range(6):
                yield Card(id=f"c{i}")
        with Horizontal(id="mid"):
            with Vertical(id="money_box"):
                yield Static(id="money_title")
                yield Sparkline([0], summary_function=max, id="spark")
            yield Static(id="skills")
            yield Static(id="cc")
        with Horizontal(id="low"):
            yield Static(id="activity")
            yield Static(id="loot")
            with VerticalScroll(id="feed"):
                yield Static(id="feed_txt")
        yield Footer()

    def on_mount(self):
        self.scope_today = True
        self.cc_cache = None
        self.last_live_check = 0
        self.live = False
        self.refresh_all()
        self.set_interval(1.5, self.refresh_all)

    def action_refresh(self): self.refresh_all()
    def action_toggle_scope(self):
        self.scope_today = not self.scope_today; self.refresh_all()

    # ---------------- data ----------------
    def refresh_all(self):
        ev = data.load_events()
        days, totals = data.summarize(ev)
        last = next((e for e in reversed(ev) if e.get("season") in data.SEASONS), {})
        now = time.time()
        if self.live or now - self.last_live_check > 30:   # old mod: ping rarely (it resets auto-pause)
            self.last_live_check = now
            self.live = data.live_ok()
        st = data.api("state") if self.live else None
        if self.live and (self.cc_cache is None or int(now) % 10 == 0):
            fresh = data.api("cc")
            if fresh:
                self.cc_cache = fresh; data.save_cc(fresh)
        if self.cc_cache is None:
            self.cc_cache = data.load_cc()
        ping = data.api("ping") if self.live else None
        p = (st or {}).get("player") or {}
        cur = {
            "season": (st or last).get("season"), "day": (st or last).get("day"), "year": (st or last).get("year") or 1,
            "time": (st or last).get("time"), "weather": (st or last).get("weather"),
            "loc": p.get("loc") or last.get("loc"), "money": p.get("money", last.get("money")),
            "stamina": p.get("stamina", last.get("stamina")), "max_stamina": p.get("max_stamina", 270),
            "health": p.get("health", last.get("health")), "max_health": p.get("max_health", 100),
            "skills": p.get("skills") or last.get("skills") or {},
            "water": next(((i.get("water"), i.get("water_max")) for i in (st or {}).get("inventory", []) if i["name"] == "Watering Can"), (last.get("can"), last.get("can_max"))),
            "inv": len((st or {}).get("inventory", [])) if st else last.get("inv_used"), "backpack": (st or last).get("backpack") or 12,
        }
        k = data.day_index(cur["season"], cur["day"], cur["year"]) if cur["season"] in data.SEASONS else None
        today = days.get(k, {})
        self.draw_banner(cur, ping)
        self.draw_cards(cur, today, days, totals)
        self.draw_money(days)
        self.draw_skills(cur)
        self.draw_cc()
        scope = today if self.scope_today else totals
        self.draw_activity(scope)
        self.draw_loot(scope, totals)
        self.draw_feed(ev)

    # ---------------- panels ----------------
    def draw_banner(self, c, ping):
        sc = SEASON_COL.get(c["season"], GOLD)
        t = Text()
        t.append(" ✦ CLAUDE PLAYS STARDEW ✦ ", style=f"bold {GOLD}")
        t.append(f"  Y{c['year']} ", style="bold white")
        t.append(f"{(c['season'] or '?').title()} {c['day']}", style=f"bold {sc}")
        t.append("  ·  ", style="#6c757d"); t.append(clock(c['time']), style="bold white"); t.append("  ·  ", style="#6c757d")
        t.append(f"{WEATHER_ICON.get(c['weather'], '?')} {c['weather'] or ''}  ", style=CYAN)
        t.append(f"📍 {c['loc'] or '?'}  ", style=PINK)
        if ping:
            t.append(f"⏩ {ping.get('speed', 1)}x ", style=f"bold {ORANGE}")
            t.append("● LIVE", style=f"bold {GREEN}")
        else:
            t.append("○ offline (log)", style="#6c757d")
        self.query_one("#banner").update(t)

    def draw_cards(self, c, today, days, totals):
        ms, me = today.get("money_start"), c["money"]
        delta = (me - ms) if (ms is not None and me is not None) else 0
        n_days = len([d for d in days.values() if d.get("money_end") is not None]) or 1
        cards = [
            ("GOLD", Text(f"{me or 0:,}g", style=f"bold {GOLD}"),
             Text(f"{'+' if delta >= 0 else ''}{delta:,}g today", style=GREEN if delta >= 0 else RED)),
            ("ENERGY", bar(c["stamina"], c["max_stamina"], 18, GREEN), Text(f"{c['stamina'] or 0:.0f} / {c['max_stamina']}", style=GREEN)),
            ("HEALTH", bar(c["health"], c["max_health"], 18, RED), Text(f"{c['health'] or 0} / {c['max_health']}", style=RED)),
            ("BACKPACK", bar(c["inv"], c["backpack"], 18, BLUE), Text(f"{c['inv'] or 0} / {c['backpack']} slots", style=BLUE)),
            ("WATERING CAN", bar(c["water"][0] or 0, c["water"][1] or 40, 18, CYAN if (c["water"][0] or 0) > 0 else RED),
             Text(("EMPTY - refill!" if c["water"][0] == 0 else f"{c['water'][0]} / {c['water'][1]}") if c["water"][0] is not None else "n/a", style=CYAN if c["water"][0] else RED)),
            ("MINES", Text(f"floor {totals['deepest']}", style=f"bold {ORANGE}"), Text(f"today ↓{today.get('deepest', 0)}", style=ORANGE)),
        ]
        for i, (title, big, small) in enumerate(cards):
            body = Text(title + "\n", style="bold #8d99ae") + big + Text("\n") + small
            self.query_one(f"#c{i}").update(body)

    def draw_money(self, days):
        series = data.money_series(days)
        vals = [v for _, v in series] or [0]
        self.query_one("#spark").data = vals
        hi = max(vals); lo = min(vals)
        self.query_one("#money_title").update(
            Text(f"💰 MONEY BY DAY   ", style=f"bold {GOLD}") + Text(f"{len(vals)} days · low {lo:,}g · high {hi:,}g · now {vals[-1]:,}g", style="#8d99ae"))

    def draw_skills(self, c):
        t = Text("🌱 SKILLS\n\n", style=f"bold {GREEN}")
        for name, col in SKILLS:
            lv = c["skills"].get(name, 0) if c["skills"] else 0
            t.append(f"{name.title():<9}", style="white"); t.append_text(bar(lv, 10, 10, col)); t.append(f" {lv}\n", style=f"bold {col}")
        self.query_one("#skills").update(t)

    def draw_cc(self):
        t = Text("🏛  COMMUNITY CENTER\n", style=f"bold {PURPLE}")
        cc = self.cc_cache
        if not cc:
            t.append("\n(needs live game)", style="#6c757d"); self.query_one("#cc").update(t); return
        core = [x for x in cc["bundles"] if x["room"] in ROOMS]
        t.append(f"{sum(x['complete'] for x in core)} / {len(core)} bundles\n\n", style="#8d99ae")
        for r in ROOMS:
            bs = [b for b in cc["bundles"] if b["room"] == r]
            if not bs: continue
            done = sum(b["complete"] for b in bs)
            is_open = any(b["open"] for b in bs)
            col = GOLD if done == len(bs) else (PURPLE if is_open else "#495057")
            t.append(f"{'★' if done == len(bs) else ('◆' if is_open else '🔒')} {r:<15}", style=col)
            t.append_text(bar(done, len(bs), 8, col)); t.append(f" {done}/{len(bs)}\n", style=col)
        self.query_one("#cc").update(t)

    def draw_activity(self, scope):
        mins = scope.get("minutes", {})
        total = sum(mins.values()) or 1
        t = Text(f"⏱  TIME USE ({'today' if self.scope_today else 'all-time'}, game hours)\n\n", style=f"bold {CYAN}")
        for cat, m in sorted(mins.items(), key=lambda x: -x[1]):
            col = data.CAT_COLOR.get(cat, "#495057")
            t.append(f"{cat:<10}", style=col); t.append_text(bar(m, total, 16, col)); t.append(f" {m/60:4.1f}h {100*m/total:3.0f}%\n", style=col)
        if not mins: t.append("no events yet", style="#6c757d")
        self.query_one("#activity").update(t)

    def draw_loot(self, scope, totals):
        t = Text("🎣 HAUL\n", style=f"bold {PINK}")
        def top(counter, title, col, n=5):
            t.append(f"\n{title}: ", style=f"bold {col}")
            if not counter: t.append("—", style="#6c757d"); return
            t.append(", ".join(f"{k}×{v}" for k, v in counter.most_common(n)), style="white")
        top(scope.get("fish", {}) and __import__("collections").Counter(scope["fish"]), "Fish", CYAN)
        top(scope.get("forage", {}) and __import__("collections").Counter(scope["forage"]), "Forage", PURPLE)
        top(scope.get("shipped", {}) and __import__("collections").Counter(scope["shipped"]), "Shipped", GOLD)
        dn = scope.get("donated", [])
        t.append("\nDonated: ", style=f"bold {GREEN}"); t.append(", ".join(f"{i}" for i, _ in dn) or "—", style="white")
        t.append(f"\n\nAll-time: {totals['harvested']} harvested · {totals['planted']} planted · {totals['watered']} watered · {totals['casts']} casts",
                 style="#8d99ae")
        self.query_one("#loot").update(t)

    def draw_feed(self, ev):
        t = Text("📜 LIVE FEED\n", style=f"bold {BLUE}")
        for e in ev[-40:][::-1]:
            msg = e.get("msg", "")
            if msg.startswith("Traceback") or msg.startswith("  "): continue
            col = data.CAT_COLOR.get(data.category(msg), "white")
            if "FAILED" in msg: col = RED
            t.append(f"{clock(e.get('time')):>8} ", style="#6c757d"); t.append((msg[:58] + ("…" if len(msg) > 58 else "")) + "\n", style=col)
        self.query_one("#feed_txt").update(t)


if __name__ == "__main__":
    StatsApp().run()
