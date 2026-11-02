"""Plan a settlement on a grid, and check it against spacing and capacity rules.

The default figures are commonly quoted planning values, based on the Sphere Handbook. They are
for a first sketch: ground, drainage, culture and safety must shape any real plan.
"""
from dataclasses import dataclass, field

import math

RULES = {"cell_m": 5.0, "people_per_shelter": 5, "people_per_latrine": 20, "people_per_tap": 250, "latrine_max_m": 50, "water_max_m": 500, "latrine_to_water_min_m": 30, "fire_break_m": 30, "area_per_person_m2": 45, "block_shelters": 16}
EMPTY, SHELTER, LATRINE, WATER, PATH, BLOCKED = ".", "S", "L", "W", "=", "#"
NAMES = {SHELTER: "Shelter", LATRINE: "Latrine", WATER: "Water point", PATH: "Path", BLOCKED: "Unusable ground"}
COLOURS = {SHELTER: "#c98a3a", LATRINE: "#7a5ea8", WATER: "#2a8fd6", PATH: "#c9ccd1", BLOCKED: "#5c6470"}


class Plan:
    def __init__(self, width, height, rules=None):
        if width < 1 or height < 1:
            raise ValueError("a plan needs at least one cell")
        self.w, self.h = width, height
        self.rules = {**RULES, **(rules or {})}
        self.grid = [[EMPTY] * width for _ in range(height)]

    def set(self, x, y, kind):
        if not (0 <= x < self.w and 0 <= y < self.h):
            raise ValueError(f"({x}, {y}) is outside the site")
        if kind not in NAMES and kind != EMPTY:
            raise ValueError(f"unknown feature {kind}")
        if self.grid[y][x] == BLOCKED and kind != EMPTY:
            raise ValueError(f"({x}, {y}) is unusable ground")
        self.grid[y][x] = kind

    def cells(self, kind):
        return [(x, y) for y in range(self.h) for x in range(self.w) if self.grid[y][x] == kind]

    def count(self, kind):
        return sum(r.count(kind) for r in self.grid)

    def people(self):
        return self.count(SHELTER) * self.rules["people_per_shelter"]

    def metres(self, a, b):
        return math.dist(a, b) * self.rules["cell_m"]

    def nearest(self, cell, others):
        return min((self.metres(cell, o) for o in others), default=math.inf)

    def text(self):
        return "\n".join("".join(r) for r in self.grid)

    @classmethod
    def from_text(cls, text, rules=None):
        rows = [r.strip() for r in text.strip().splitlines()]
        if len({len(r) for r in rows}) != 1:
            raise ValueError("every row must have the same length")
        p = cls(len(rows[0]), len(rows), rules)
        for y, r in enumerate(rows):
            for x, c in enumerate(r):
                if c != EMPTY:
                    p.grid[y][x] = c if c in NAMES else (_ for _ in ()).throw(ValueError(f"unknown feature {c}"))
        return p

    def svg(self, size=14):
        out = [f'<svg viewBox="0 0 {self.w * size} {self.h * size}" width="100%" role="img">']
        for y in range(self.h):
            for x in range(self.w):
                c = self.grid[y][x]
                if c != EMPTY:
                    out.append(f'<rect x="{x * size}" y="{y * size}" width="{size - 1}" height="{size - 1}" fill="{COLOURS[c]}"></rect>')
        out.append("</svg>")
        return "".join(out)


def check(plan):
    """Return (summary, problems). Each problem is (rule, message, cell or None)."""
    r = plan.rules
    people = plan.people()
    shelters, latrines, water = plan.cells(SHELTER), plan.cells(LATRINE), plan.cells(WATER)
    problems = []
    need_lat = math.ceil(people / r["people_per_latrine"])
    if len(latrines) < need_lat:
        problems.append(("latrines", f"{len(latrines)} latrines for {people} people, {need_lat} needed", None))
    need_tap = math.ceil(people / r["people_per_tap"])
    if len(water) < need_tap:
        problems.append(("water", f"{len(water)} water points for {people} people, {need_tap} needed", None))
    for s in shelters:
        d = plan.nearest(s, latrines)
        if latrines and d > r["latrine_max_m"]:
            problems.append(("latrine distance", f"shelter at {s} is {d:.0f} m from a latrine", s))
        d = plan.nearest(s, water)
        if water and d > r["water_max_m"]:
            problems.append(("water distance", f"shelter at {s} is {d:.0f} m from water", s))
    for l in latrines:
        d = plan.nearest(l, water)
        if d < r["latrine_to_water_min_m"]:
            problems.append(("contamination", f"latrine at {l} is only {d:.0f} m from a water point", l))
    area = plan.w * plan.h * r["cell_m"] ** 2
    per = area / people if people else None
    if per is not None and per < r["area_per_person_m2"]:
        problems.append(("crowding", f"{per:.0f} m² per person, target {r['area_per_person_m2']} m²", None))
    largest = largest_block(plan)
    if largest > r["block_shelters"] * 15:
        problems.append(("fire", f"{largest} shelters with no fire break between them", None))
    reach = reachable(plan)
    cut_off = [s for s in shelters if s not in reach]
    if plan.count(PATH) and cut_off:
        problems.append(("access", f"{len(cut_off)} shelters cannot be reached along paths or open ground", cut_off[0]))
    return {"people": people, "shelters": len(shelters), "latrines": len(latrines), "water_points": len(water), "area_m2": area, "area_per_person": per}, problems


def largest_block(plan):
    """The largest group of shelters connected without crossing a gap, a path or blocked ground."""
    seen = set()
    best = 0
    for start in plan.cells(SHELTER):
        if start in seen:
            continue
        stack, size = [start], 0
        seen.add(start)
        while stack:
            x, y = stack.pop()
            size += 1
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                n = (x + dx, y + dy)
                if 0 <= n[0] < plan.w and 0 <= n[1] < plan.h and n not in seen and plan.grid[n[1]][n[0]] == SHELTER:
                    seen.add(n)
                    stack.append(n)
        best = max(best, size)
    return best


def reachable(plan):
    """Cells that can be reached on foot from the site edge. Shelters are destinations, not routes."""
    walk = (EMPTY, PATH)
    start = [(x, y) for y in range(plan.h) for x in range(plan.w) if (x in (0, plan.w - 1) or y in (0, plan.h - 1)) and plan.grid[y][x] != BLOCKED]
    seen = set(start)
    stack = [c for c in start if plan.grid[c[1]][c[0]] in walk]
    while stack:
        x, y = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if 0 <= n[0] < plan.w and 0 <= n[1] < plan.h and n not in seen and plan.grid[n[1]][n[0]] != BLOCKED:
                seen.add(n)
                if plan.grid[n[1]][n[0]] in walk:
                    stack.append(n)
    return seen


def auto_layout(width, height, people, blocked=(), rules=None):
    """Lay out rows of shelter blocks with paths, then place latrines and water points by the rules.
    A first draft to edit. Returns a Plan and how many people it could not fit."""
    plan = Plan(width, height, rules)
    r = plan.rules
    for x, y in blocked:
        plan.grid[y][x] = BLOCKED
    block_w, block_h = 4, 2
    for y in range(0, height):
        if y % (block_h + 1) == 2:
            for x in range(width):
                if plan.grid[y][x] == EMPTY:
                    plan.grid[y][x] = PATH
    for x in range(0, width):
        if x % (block_w + 2) == 5:
            for y in range(height):
                if plan.grid[y][x] == EMPTY:
                    plan.grid[y][x] = PATH
    free = plan.cells(EMPTY)
    want = math.ceil(people / r["people_per_shelter"])
    # one cell in six stays free for latrines and water
    placed = 0
    kept = []
    for i, (x, y) in enumerate(free):
        if i % 6 == 5 or placed >= want:
            kept.append((x, y))
        else:
            plan.grid[y][x] = SHELTER
            placed += 1
    need_w = math.ceil(plan.people() / r["people_per_tap"])
    need_l = math.ceil(plan.people() / r["people_per_latrine"])
    water = []
    for c in sorted(kept, key=lambda c: abs(c[0] - width / 2) + abs(c[1] - height / 2)):
        if len(water) >= need_w:
            break
        if all(plan.metres(c, w) > 20 for w in water):
            plan.grid[c[1]][c[0]] = WATER
            water.append(c)
    spots = [c for c in kept if plan.grid[c[1]][c[0]] == EMPTY and plan.nearest(c, water) >= r["latrine_to_water_min_m"]]
    shelters = plan.cells(SHELTER)
    placed_l = []
    uncovered = list(shelters)
    while len(placed_l) < need_l and spots:
        best = max(spots, key=lambda c: (sum(1 for s in uncovered if plan.metres(s, c) <= r["latrine_max_m"]), -abs(c[0] - width / 2)))
        spots.remove(best)
        plan.grid[best[1]][best[0]] = LATRINE
        placed_l.append(best)
        uncovered = [s for s in uncovered if plan.metres(s, best) > r["latrine_max_m"]]
    return plan, max(0, people - plan.people())
