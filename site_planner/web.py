"""The offline web app."""
from . import core
from .fieldkit import App, Fail, Raw, card, form, h, link, redirect, stats, table

SCHEMA = "CREATE TABLE IF NOT EXISTS plans (id INTEGER PRIMARY KEY, name TEXT NOT NULL, layout TEXT NOT NULL);"


def create_app(db="siteplan.db"):
    a = App("Site Planner", db, SCHEMA, [("Plans", "/"), ("New plan", "/new")])

    def load(pid):
        r = a.row("SELECT * FROM plans WHERE id = ?", pid)
        if r is None:
            raise Fail("No such plan", 404)
        return r, core.Plan.from_text(r["layout"])

    @a.route("/")
    def home(req):
        return a.page("Plans", card("Plans", table(a.rows("SELECT id, name FROM plans ORDER BY id DESC"), [("Plan", lambda r: link(f"/plan/{r['id']}", r["name"]))], "Create a plan to begin.")))

    @a.route("/new", ("GET", "POST"))
    def new(req):
        if req.method == "POST":
            w, h_ = int(req.number("width", low=4, high=200)), int(req.number("height", low=4, high=200))
            plan, missed = core.auto_layout(w, h_, int(req.number("people", low=0, high=200000)))
            cur = a.run("INSERT INTO plans (name, layout) VALUES (?, ?)", req.text("name"), plan.text())
            return redirect(f"/plan/{cur.lastrowid}?missed={missed}")
        return a.page("New plan", card("Draft a layout. Each cell is 5 m by 5 m.", form(a, "/new", [("name", "Site name"), ("width", "Width in cells", "number", 40), ("height", "Height in cells", "number", 30), ("people", "People to shelter", "number", 500)], "Draft")))

    @a.route("/plan/<id>", ("GET", "POST"))
    def plan(req, id):
        r, p = load(id)
        if req.method == "POST":
            kind = req.text("kind")
            try:
                p.set(int(req.number("x")), int(req.number("y")), kind)
            except ValueError as exc:
                raise Fail(str(exc)) from None
            a.run("UPDATE plans SET layout = ? WHERE id = ?", p.text(), id)
            return redirect(f"/plan/{id}")
        info, problems = core.check(p)
        missed = int(req.get("missed") or 0)
        legend = " ".join(f'<span style="color:{core.COLOURS[k]}">■</span> {h(v)}' for k, v in core.NAMES.items())
        body = stats([("People", info["people"]), ("Shelters", info["shelters"]), ("Latrines", info["latrines"]), ("Water points", info["water_points"]), ("m² a person", "n/a" if info["area_per_person"] is None else f"{info['area_per_person']:.0f}")])
        body += card("Layout", p.svg() + f"<p>{legend}</p>")
        kinds = [(k, v) for k, v in core.NAMES.items()] + [(core.EMPTY, "Clear")]
        body += card("Change a cell", form(a, f"/plan/{id}", [("x", "Column (from 0)", "number"), ("y", "Row (from 0)", "number"), ("kind", "Feature", "select", kinds)], "Apply"))
        body += card(f"Problems ({len(problems)})", table(problems[:60], [("Rule", lambda x: x[0]), ("Detail", lambda x: x[1])], "No rule problems found. Walk the ground before relying on this."))
        return a.page(r["name"], body, f"{missed} people could not fit on this site." if missed else "")

    return a
