"""
E₀ — Visual Traffic Demo: BFS shortest path vs greedy vs E₀
=============================================================

Runs the C185 traffic simulation on **both** topologies, three strategies
each, all from the same seed, records every tick, and bakes the recording
into one self-contained HTML file.

Both topologies are included on purpose:

  Uniform grid  — E₀ roughly doubles BFS throughput. The mechanism is that
                  rigid shortest-path routing sends every vehicle through
                  the same bottleneck and per-vehicle memory does not.

  River city    — E₀ **loses** on completed trips. Learned congestion costs
                  outlive the congestion, so vehicles drift sideways to
                  avoid a bridge that is now free. This is C185 Finding 5,
                  a confirmed limitation, and it is shown rather than
                  omitted.

The simulation is the real one from ``explore_traffic``. Nothing is
re-implemented in JavaScript; the page is a player for recorded frames.

Usage::

    py -3 -m e0_controller.demo_traffic_visual
    py -3 -m e0_controller.demo_traffic_visual --ticks 600 --vehicles 24
    py -3 -m e0_controller.demo_traffic_visual --out somewhere/else.html

Default output is ``server/static/traffic_demo.html``, which the Domain
Studio server serves at ``http://localhost:8765/studio/traffic_demo.html``.
The file has no external dependencies and opens fine straight from disk.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from e0_controller.explore_traffic import (
    CityGrid,
    SimResult,
    Strategy,
    bfs_next_hop,
    parse_node,
    run_simulation,
)

DEFAULT_TICKS = 400
DEFAULT_VEHICLES = 20
DEFAULT_SEED = 42
DEFAULT_OUT = Path("server/static/traffic_demo.html")

RIVER_ROW = 3
BRIDGE_COLS = (2, 5)


# ──────────────────────────────────────────────────────────────────
# Recording
# ──────────────────────────────────────────────────────────────────

@dataclass
class Recording:
    """A replayable run, in a form that survives JSON."""

    label: str
    blurb: str
    node_index: Dict[str, int]
    vehicles: List[str]
    frames: List[Dict[str, object]]
    trips: int
    stuck: int
    overrides: int
    throughput: float
    avg_trip_time: float

    def to_json(self) -> dict:
        return {
            "label": self.label,
            "blurb": self.blurb,
            "vehicles": self.vehicles,
            "frames": self.frames,
            "trips": self.trips,
            "stuck": self.stuck,
            "overrides": self.overrides,
            "throughput": round(self.throughput, 1),
            "avgTripTime": round(self.avg_trip_time, 2),
        }


def _record(
    result: SimResult,
    city: CityGrid,
    label: str,
    blurb: str,
) -> Recording:
    """Compress a SimResult into per-tick frames of node indices."""
    node_index = {n: i for i, n in enumerate(city.nodes)}

    seen: List[str] = []
    for snap in result.snapshots:
        for name in snap.positions:
            if name not in seen:
                seen.append(name)
    seen.sort(key=lambda s: int(s[1:]))

    frames: List[Dict[str, object]] = []
    for snap in result.snapshots:
        frames.append(
            {
                "t": snap.tick,
                # -1 marks a vehicle that has not spawned into `positions` yet
                "p": [node_index.get(snap.positions.get(v, ""), -1) for v in seen],
                "c": [node_index[n] for n in snap.congested],
                "trips": snap.trips_so_far,
            }
        )

    return Recording(
        label=label,
        blurb=blurb,
        node_index=node_index,
        vehicles=seen,
        frames=frames,
        trips=result.trips_completed,
        stuck=result.total_stuck,
        overrides=result.total_overrides,
        throughput=result.throughput_per_100,
        avg_trip_time=result.avg_trip_time,
    )


STRATEGIES = [
    (
        Strategy.BFS_SHORTEST,
        "BFS shortest path",
        "Precomputed optimal routes, recomputed for nothing. Every vehicle with "
        "the same goal takes the same corridor.",
    ),
    (
        Strategy.GREEDY_DELTA,
        "Greedy Δ (no memory)",
        "Always step toward the goal. Retries a blocked move forever, which "
        "turns out to matter.",
    ),
    (
        Strategy.E0_CONSERVATIVE,
        "E₀ (memory + gated overlay)",
        "Each vehicle remembers its own jams. A 3-hop amplitude overlay may "
        "override the greedy choice, but only above 0.85 confidence.",
    ),
]


@dataclass
class Scenario:
    """One topology, run under every strategy."""

    key: str
    title: str
    intro: str
    verdict: str
    city: CityGrid
    river_row: int          # -1 when the topology has no river
    recordings: List[Recording]


def _run_city(
    city: CityGrid, ticks: int, vehicles: int, seed: int
) -> List[Recording]:
    bfs_table = bfs_next_hop(city)
    out: List[Recording] = []
    for strategy, label, blurb in STRATEGIES:
        random.seed(seed)      # identical spawns and goals across strategies
        result = run_simulation(
            city,
            n_vehicles=vehicles,
            n_ticks=ticks,
            strategy=strategy,
            bfs_table=bfs_table,
            snapshot_interval=1,
        )
        out.append(_record(result, city, label, blurb))
        print(
            f"    {label:<32} trips={result.trips_completed:>4}  "
            f"stuck={result.total_stuck:>5}  "
            f"thru/100={result.throughput_per_100:>6.1f}  "
            f"overrides={result.total_overrides}"
        )
    return out


def run_scenarios(
    ticks: int = DEFAULT_TICKS,
    vehicles: int = DEFAULT_VEHICLES,
    seed: int = DEFAULT_SEED,
) -> List[Scenario]:
    """Run every strategy on both topologies, recording each tick."""
    scenarios: List[Scenario] = []

    print("  Uniform grid (5×4, central bottleneck)")
    grid = CityGrid.build()
    scenarios.append(
        Scenario(
            key="grid",
            title="Uniform grid — where E₀ wins",
            intro=(
                "5×4 city, all intersections capacity 3 except the two central "
                "ones, which hold a single vehicle. Every crossing route wants "
                "to pass through the middle."
            ),
            verdict=(
                "Mechanism: rigid shortest-path routing funnels every vehicle into "
                "the same bottleneck and keeps doing so, because the shortest route "
                "does not change when it fills up. Per-vehicle memory spreads the "
                "load — a vehicle that fails at the centre raises its own cost for "
                "that edge and goes around — and the overlay catches some jams one "
                "hop before they happen."
            ),
            city=grid,
            river_row=-1,
            recordings=_run_city(grid, ticks, vehicles, seed),
        )
    )

    print("  River city (6×8, two bridges)")
    river = CityGrid.build_river_city(
        rows=6, cols=8, river_row=RIVER_ROW, bridge_cols=set(BRIDGE_COLS)
    )
    scenarios.append(
        Scenario(
            key="river",
            title="River city — where E₀ loses",
            intro=(
                "6×8 city, a river at row 3, two bridges of capacity 1. Every "
                "north–south trip must cross one of them. This topology is a "
                "confirmed limitation, not a showcase."
            ),
            verdict=(
                "Mechanism: the chokepoint is mandatory here — you cannot route "
                "around a bridge, you can only queue for it. Learned congestion "
                "then outlives the congestion: after failing at a bridge, an "
                "adaptive vehicle's cost for that edge stays elevated, so it "
                "drifts sideways along the bank, and sideways never crosses the "
                "river. Watch the blocked counters against the trip counters. The "
                "adaptive strategies block far less and still move less traffic, "
                "because queueing at the bridge IS the correct behaviour. Avoiding "
                "collisions is not the same as making progress. The fix is in the "
                "memory, not the lookahead: decay the learned costs so a bridge "
                "that cleared ten ticks ago stops looking expensive."
            ),
            city=river,
            river_row=RIVER_ROW,
            recordings=_run_city(river, ticks, vehicles, seed),
        )
    )

    return scenarios


# ──────────────────────────────────────────────────────────────────
# HTML emission
# ──────────────────────────────────────────────────────────────────

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>E0 - Traffic under congestion: BFS vs greedy vs E0</title>
<style>
  :root {
    --bg: #ffffff; --fg: #16181d; --muted: #6b7280; --line: #e3e6ea;
    --panel: #f7f8fa; --road: #dfe3e8; --river: #cfe0f3; --bridge: #f2c94c;
    --veh: #2563eb; --jam: #dc2626; --ok: #16a34a; --accent: #7c3aed;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0f1115; --fg: #e6e8ec; --muted: #9aa3ae; --line: #262a31;
      --panel: #171a20; --road: #2a2f38; --river: #1c2c42; --bridge: #b8860b;
      --veh: #60a5fa; --jam: #f87171; --ok: #4ade80; --accent: #a78bfa;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 24px; background: var(--bg); color: var(--fg);
    font: 15px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  .wrap { max-width: 1080px; margin: 0 auto; }
  h1 { font-size: 22px; margin: 0 0 6px; letter-spacing: -0.01em; }
  .sub { color: var(--muted); margin: 0 0 20px; font-size: 14px; }
  .sims { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
  .sim {
    border: 1px solid var(--line); border-radius: 10px;
    background: var(--panel); padding: 14px;
  }
  .sim h3 { font-size: 15px; margin: 0 0 4px; font-weight: 600; }
  .sc-title {
    font-size: 18px; margin: 34px 0 4px; padding-top: 22px;
    border-top: 1px solid var(--line);
  }
  .sc-intro { color: var(--muted); font-size: 14px; margin: 0 0 16px; max-width: 62ch; }
  .result { font-size: 14px; margin: 14px 0 0; max-width: 68ch; }
  tr.win td { font-weight: 600; }
  tr.win td:first-child::after { content: " ←"; color: var(--ok); }
  .sim .blurb { color: var(--muted); font-size: 13px; margin: 0 0 12px; min-height: 3em; }
  canvas { width: 100%; height: auto; display: block; border-radius: 6px; }
  .stats { display: flex; gap: 18px; margin-top: 12px; flex-wrap: wrap; }
  .stat { font-variant-numeric: tabular-nums; }
  .stat b { display: block; font-size: 20px; font-weight: 600; }
  .stat span { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
  .good b { color: var(--ok); }
  .bad b { color: var(--jam); }
  .controls {
    display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
    margin: 20px 0; padding: 14px; border: 1px solid var(--line);
    border-radius: 10px; background: var(--panel);
  }
  button {
    font: inherit; font-weight: 550; padding: 7px 16px; cursor: pointer;
    border: 1px solid var(--line); border-radius: 7px;
    background: var(--bg); color: var(--fg);
  }
  button:hover { border-color: var(--accent); color: var(--accent); }
  input[type=range] { flex: 1; min-width: 160px; accent-color: var(--accent); }
  .tick { font-variant-numeric: tabular-nums; color: var(--muted); min-width: 110px; font-size: 13px; }
  .legend { display: flex; gap: 16px; flex-wrap: wrap; margin: 4px 0 20px; font-size: 13px; color: var(--muted); }
  .legend i { display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; }
  .note {
    border-left: 3px solid var(--accent); padding: 2px 0 2px 14px;
    color: var(--muted); font-size: 14px; margin: 18px 0 0; max-width: 68ch;
  }
  .note strong { color: var(--fg); }
  table { border-collapse: collapse; width: 100%; margin-top: 12px; font-size: 14px; }
  th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--line); }
  th { font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); font-weight: 550; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  .scroll { overflow-x: auto; }
  footer { margin-top: 28px; padding-top: 16px; border-top: 1px solid var(--line); color: var(--muted); font-size: 13px; }
  a { color: var(--accent); }
</style>
</head>
<body>
<div class="wrap">
  <h1>Traffic under congestion &mdash; shortest paths vs greedy vs E&#8320;</h1>
  <p class="sub">
    Two topologies, three routing strategies, one seed. Same spawns, same goals,
    same congestion model in every run &mdash; only the routing differs.
    <strong>The first topology suits E&#8320; and the second defeats it</strong>, and
    both are here because a benchmark that only shows its wins is not a benchmark.
  </p>

  <div class="legend">
    <span><i style="background:var(--road)"></i>road</span>
    <span><i style="background:var(--river)"></i>river</span>
    <span><i style="background:var(--bridge)"></i>chokepoint (capacity 1)</span>
    <span><i style="background:var(--veh)"></i>vehicle</span>
    <span><i style="background:var(--jam)"></i>at capacity</span>
  </div>

  <div class="controls">
    <button id="play">Pause</button>
    <button id="restart">Restart</button>
    <input id="scrub" type="range" min="0" value="0">
    <span class="tick" id="tick">tick 0</span>
    <label style="font-size:13px;color:var(--muted)">
      speed
      <input id="speed" type="range" min="1" max="60" value="18" style="width:90px">
    </label>
  </div>

  <div id="scenarios"></div>

  <footer>
    Generated by <code>py -3 -m e0_controller.demo_traffic_visual</code> from the real
    simulation in <code>e0_controller/explore_traffic.py</code>. Frames are recorded,
    not re-simulated in the browser. Single seed &mdash; the published figures are
    5-seed averages and this topology shows real seed variance.
    See <a href="https://github.com/Thomas66690815/E0-Framework">E&#8320; Framework</a>
    and <code>docs/research/C185_TRAFFIC_VALIDATION_REPORT_v1.md</code>.
  </footer>
</div>

<script id="data" type="application/json">__DATA__</script>
<script>
(function () {
  var D = JSON.parse(document.getElementById("data").textContent);
  var PAD = 14;

  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  function esc(s) {
    return String(s).replace(/[&<>]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c];
    });
  }

  var maxFrame = Infinity;
  D.scenarios.forEach(function (sc) {
    sc.runs.forEach(function (r) {
      maxFrame = Math.min(maxFrame, r.frames.length - 1);
    });
  });

  var host = document.getElementById("scenarios");
  var views = [];

  D.scenarios.forEach(function (sc) {
    var cell = sc.cols > 6 ? 38 : 46;
    var W = sc.cols * cell + PAD * 2, H = sc.rows * cell + PAD * 2;

    var sec = document.createElement("section");
    sec.innerHTML =
      '<h2 class="sc-title">' + esc(sc.title) + '</h2>' +
      '<p class="sc-intro">' + esc(sc.intro) + '</p>' +
      '<div class="sims"></div>' +
      '<div class="scroll"><table class="final"></table></div>' +
      '<p class="result"></p>' +
      '<p class="note">' + esc(sc.verdict) + '</p>';
    host.appendChild(sec);

    var sims = sec.querySelector(".sims");
    sc.runs.forEach(function (run) {
      var el = document.createElement("div");
      el.className = "sim";
      el.innerHTML =
        '<h3>' + esc(run.label) + '</h3>' +
        '<p class="blurb">' + esc(run.blurb) + '</p>' +
        '<canvas width="' + W + '" height="' + H + '"></canvas>' +
        '<div class="stats">' +
          '<div class="stat good"><b data-trips>0</b><span>trips</span></div>' +
          '<div class="stat bad"><b data-jam>0</b><span>blocked now</span></div>' +
          '<div class="stat"><b>' + run.overrides + '</b><span>overrides</span></div>' +
        '</div>';
      sims.appendChild(el);
      views.push({
        sc: sc, run: run, cell: cell, W: W, H: H,
        ctx: el.querySelector("canvas").getContext("2d"),
        trips: el.querySelector("[data-trips]"),
        jam: el.querySelector("[data-jam]"),
      });
    });

    var best = Math.max.apply(null, sc.runs.map(function (r) { return r.trips; }));
    var rows = ['<tr><th>Strategy</th><th class="num">Trips</th>' +
                '<th class="num">Throughput / 100</th><th class="num">Avg trip</th>' +
                '<th class="num">Stuck</th><th class="num">Overrides</th></tr>'];
    sc.runs.forEach(function (r) {
      var mark = r.trips === best ? ' class="win"' : '';
      rows.push('<tr' + mark + '><td>' + esc(r.label) + '</td>' +
        '<td class="num">' + r.trips + '</td>' +
        '<td class="num">' + r.throughput + '</td>' +
        '<td class="num">' + r.avgTripTime + '</td>' +
        '<td class="num">' + r.stuck + '</td>' +
        '<td class="num">' + r.overrides + '</td></tr>');
    });
    sec.querySelector(".final").innerHTML = rows.join("");

    // Stated from the numbers actually produced, so it cannot go stale
    // when the run is regenerated with a different seed or tick count.
    var byTrips = sc.runs.slice().sort(function (a, b) { return b.trips - a.trips; });
    var byStuck = sc.runs.slice().sort(function (a, b) { return a.stuck - b.stuck; });
    var win = byTrips[0], lose = byTrips[byTrips.length - 1];
    var calm = byStuck[0];
    var ratio = lose.trips > 0 ? (win.trips / lose.trips).toFixed(2) : "n/a";
    var line =
      "This run: <strong>" + esc(win.label) + "</strong> moved the most traffic (" +
      win.trips + " trips, " + ratio + "× the worst at " + lose.trips + "). " +
      "<strong>" + esc(calm.label) + "</strong> blocked least (" + calm.stuck + ").";
    if (win.label !== calm.label) {
      line += " Those are different strategies — that gap is the point.";
    }
    sec.querySelector(".result").innerHTML = line;
  });

  function draw(view, f) {
    var sc = view.sc, ctx = view.ctx, cell = view.cell;
    var frame = view.run.frames[f];
    var roadC = css("--road"), riverC = css("--river"), bridgeC = css("--bridge");
    var vehC = css("--veh"), jamC = css("--jam"), panelC = css("--panel");

    ctx.fillStyle = panelC;
    ctx.fillRect(0, 0, view.W, view.H);

    if (sc.riverRow >= 0) {
      ctx.fillStyle = riverC;
      ctx.fillRect(PAD - 4, PAD + sc.riverRow * cell - 2, sc.cols * cell + 8, cell + 4);
    }

    var jammed = {};
    frame.c.forEach(function (i) { jammed[i] = true; });

    for (var i = 0; i < sc.nodes.length; i++) {
      var n = sc.nodes[i];
      var x = PAD + n[1] * cell, y = PAD + n[0] * cell;
      ctx.fillStyle = jammed[i] ? jamC : (sc.choke.indexOf(i) >= 0 ? bridgeC : roadC);
      ctx.beginPath();
      ctx.roundRect(x + 3, y + 3, cell - 6, cell - 6, 5);
      ctx.fill();
    }

    // vehicles, fanned inside the cell so stacked ones stay countable
    var counts = {};
    ctx.fillStyle = vehC;
    var r = cell > 40 ? 6 : 5;
    for (var v = 0; v < frame.p.length; v++) {
      var idx = frame.p[v];
      if (idx < 0) continue;
      var node = sc.nodes[idx];
      var k = counts[idx] || 0;
      counts[idx] = k + 1;
      var ang = k * 2.0944;                       // 120° apart
      var off = k === 0 ? 0 : cell * 0.17;
      var cx = PAD + node[1] * cell + cell / 2 + Math.cos(ang) * off;
      var cy = PAD + node[0] * cell + cell / 2 + Math.sin(ang) * off;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fill();
    }

    view.trips.textContent = frame.trips;
    view.jam.textContent = frame.c.length;
  }

  var f = 0, playing = true, fps = 18, acc = 0, last = 0;
  var scrub = document.getElementById("scrub");
  var tickLabel = document.getElementById("tick");
  var playBtn = document.getElementById("play");
  scrub.max = maxFrame;

  function render() {
    views.forEach(function (v) { draw(v, f); });
    scrub.value = f;
    tickLabel.textContent = "tick " + views[0].run.frames[f].t + " / " + maxFrame;
  }

  function loop(ts) {
    if (!last) last = ts;
    var dt = ts - last; last = ts;
    if (playing) {
      acc += dt;
      var step = 1000 / fps;
      while (acc >= step) {
        acc -= step;
        f = f + 1 > maxFrame ? 0 : f + 1;
      }
      render();
    }
    requestAnimationFrame(loop);
  }

  playBtn.onclick = function () {
    playing = !playing;
    playBtn.textContent = playing ? "Pause" : "Play";
  };
  document.getElementById("restart").onclick = function () { f = 0; render(); };
  scrub.oninput = function () {
    playing = false; playBtn.textContent = "Play"; f = +scrub.value; render();
  };
  document.getElementById("speed").oninput = function () { fps = +this.value; };

  render();
  requestAnimationFrame(loop);
})();
</script>
</body>
</html>
"""


def build_html(scenarios: List[Scenario]) -> str:
    """Bake every scenario into one self-contained page."""
    blocks = []
    for sc in scenarios:
        min_cap = min(sc.city.capacity.values())
        choke = [
            i
            for i, n in enumerate(sc.city.nodes)
            if sc.city.capacity.get(n, 99) == min_cap
        ]
        blocks.append(
            {
                "key": sc.key,
                "title": sc.title,
                "intro": sc.intro,
                "verdict": sc.verdict,
                "rows": sc.city.rows,
                "cols": sc.city.cols,
                "riverRow": sc.river_row,
                "nodes": [list(parse_node(n)) for n in sc.city.nodes],
                "choke": choke,
                "runs": [r.to_json() for r in sc.recordings],
            }
        )

    data = json.dumps({"scenarios": blocks}, separators=(",", ":"))
    # The payload lands inside a <script type="application/json"> block, so the
    # only sequence that could break out is a literal closing script tag.
    data = data.replace("</", "<\\/")
    return _PAGE.replace("__DATA__", data)


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Visual traffic demo: BFS vs greedy vs E0")
    ap.add_argument("--ticks", type=int, default=DEFAULT_TICKS)
    ap.add_argument("--vehicles", type=int, default=DEFAULT_VEHICLES)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    print(f"{args.vehicles} vehicles, {args.ticks} ticks, seed {args.seed}")
    scenarios = run_scenarios(args.ticks, args.vehicles, args.seed)

    html = build_html(scenarios)
    out = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    size_kb = len(html.encode("utf-8")) / 1024
    print(f"\nWrote {out}  ({size_kb:.0f} KB, self-contained)")
    print(f"  open directly, or serve it:  py -3 -m uvicorn server.main:app --port 8765")
    print(f"  then  http://localhost:8765/studio/{out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
