import unittest

from site_planner import core, create_app
from site_planner.core import LATRINE, PATH, SHELTER, WATER, Plan, auto_layout, check, largest_block, reachable


def rules(p):
    return {x[0] for x in check(p)[1]}


class TestPlan(unittest.TestCase):
    def test_bounds_and_kinds(self):
        p = Plan(4, 4)
        with self.assertRaises(ValueError):
            p.set(9, 0, SHELTER)
        with self.assertRaises(ValueError):
            p.set(0, 0, "Z")
        with self.assertRaises(ValueError):
            Plan(0, 3)

    def test_blocked_ground(self):
        p = Plan(3, 3)
        p.set(1, 1, core.BLOCKED)
        with self.assertRaises(ValueError):
            p.set(1, 1, SHELTER)

    def test_text_round_trip(self):
        t = "S.L\n.=.\nW#."
        self.assertEqual(Plan.from_text(t).text(), t)
        with self.assertRaises(ValueError):
            Plan.from_text("S.\n.")
        with self.assertRaises(ValueError):
            Plan.from_text("Z")

    def test_svg(self):
        self.assertEqual(Plan.from_text("S.").svg().count("<rect"), 1)


class TestChecks(unittest.TestCase):
    def test_too_few_latrines_and_water(self):
        p = Plan(30, 10)
        for x in range(6):
            p.set(x, 0, SHELTER)
        self.assertIn("latrines", rules(p))
        self.assertIn("water", rules(p))

    def test_counts_round_up(self):
        p = Plan(30, 30)
        for x in range(5):
            p.set(x, 0, SHELTER)
        p.set(9, 9, LATRINE)
        self.assertIn("2 needed", " ".join(m for _, m, _ in check(p)[1]))

    def test_latrine_near_water_is_flagged(self):
        p = Plan(20, 20)
        p.set(0, 0, LATRINE)
        p.set(3, 0, WATER)
        self.assertIn("contamination", rules(p))
        q = Plan(20, 20)
        q.set(0, 0, LATRINE)
        q.set(7, 0, WATER)
        self.assertNotIn("contamination", rules(q))

    def test_distance_to_latrine(self):
        p = Plan(30, 5)
        p.set(0, 0, SHELTER)
        p.set(11, 0, LATRINE)
        p.set(25, 0, WATER)
        self.assertIn("latrine distance", rules(p))

    def test_crowding(self):
        p = Plan(4, 4)
        for x in range(4):
            for y in range(4):
                p.set(x, y, SHELTER)
        self.assertIn("crowding", rules(p))

    def test_fire_break(self):
        p = Plan(20, 20)
        for x in range(20):
            for y in range(20):
                p.set(x, y, SHELTER)
        self.assertEqual(largest_block(p), 400)
        self.assertIn("fire", rules(p))
        for y in range(20):
            p.set(10, y, PATH)
        self.assertEqual(largest_block(p), 200)

    def test_access(self):
        p = Plan.from_text("......\n.SSSS.\n.S==S.\n.SSSS.\n......")
        self.assertEqual(len(reachable(p)), 30 - 2)
        q = Plan.from_text("###\n#S#\n#=#\n###")
        self.assertIn("access", rules(q))

    def test_summary(self):
        s, _ = check(Plan.from_text("SS\n.."))
        self.assertEqual((s["people"], s["shelters"], s["area_m2"]), (10, 2, 100))


class TestAutoLayout(unittest.TestCase):
    def test_small_site_meets_the_rules(self):
        p, missed = auto_layout(60, 48, 500)
        self.assertEqual(missed, 0)
        self.assertEqual(rules(p) - {"crowding"}, set())
        self.assertGreaterEqual(p.people(), 500)

    def test_paths_exist_and_keep_shelters_reachable(self):
        p, _ = auto_layout(40, 30, 300)
        self.assertGreater(p.count(PATH), 50)
        reach = reachable(p)
        self.assertTrue(all(s in reach for s in p.cells(SHELTER)))

    def test_reports_people_who_cannot_fit(self):
        p, missed = auto_layout(8, 8, 5000)
        self.assertGreater(missed, 4000)

    def test_keeps_off_blocked_ground(self):
        blocked = [(x, 5) for x in range(10)]
        p, _ = auto_layout(30, 20, 200, blocked)
        for x, y in blocked:
            self.assertEqual(p.grid[y][x], core.BLOCKED)

    def test_nothing_to_house(self):
        p, missed = auto_layout(10, 10, 0)
        self.assertEqual((p.count(SHELTER), missed), (0, 0))


class TestApp(unittest.TestCase):
    def setUp(self):
        self.a = create_app(":memory:")

    def test_flow(self):
        r = self.a.post("/new", name="North", width=40, height=30, people=300)
        self.assertEqual(r.status, 303)
        page = self.a.get(r.headers["Location"]).body.decode()
        self.assertIn("<svg", page)
        self.assertIn("Shelters", page)
        self.assertIn("North", self.a.get("/").body.decode())

    def test_editing_a_cell(self):
        url = self.a.post("/new", name="N", width=10, height=10, people=10).headers["Location"].split("?")[0]
        self.assertEqual(self.a.post(url, x=0, y=0, kind=core.BLOCKED).status, 303)
        self.assertEqual(self.a.post(url, x=99, y=0, kind=SHELTER).status, 400)
        self.assertEqual(self.a.post(url, x=0, y=0, kind=SHELTER).status, 400)

    def test_overflow_warning(self):
        r = self.a.post("/new", name="N", width=8, height=8, people=5000)
        self.assertIn("could not fit", self.a.get(r.headers["Location"]).body.decode())

    def test_missing(self):
        self.assertEqual(self.a.get("/plan/9").status, 404)
        self.assertEqual(self.a.post("/new", name="x", width=1, height=1, people=1).status, 400)


if __name__ == "__main__":
    unittest.main()
