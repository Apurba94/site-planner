# Site Planner

Sketch a settlement on a simple grid and check it against spacing and capacity rules, in seconds and offline. It can also draft a first layout for you to change.

```
python -m site_planner
```

Then open http://127.0.0.1:8036. It needs Python 3.10 or newer.

## What it checks

| Rule | Default |
|---|---|
| Latrines | One for each 20 people, within 50 m of a shelter |
| Water | One point for each 250 people, within 500 m |
| Contamination | A latrine at least 30 m from a water point |
| Space | 45 m² of site per person |
| Fire | No huge block of shelters without a gap |
| Access | Every shelter can be reached on foot |

These are commonly quoted planning figures, based on the Sphere Handbook. They live in `RULES` in `core.py`, and each site should set its own with its shelter and WASH leads.

## How it works

The site is a grid of 5 m cells, shown as a drawing and stored as plain text. `auto_layout` draws paths, fills blocks with shelters, places water near the centre, then adds latrines where they serve the most shelters while staying clear of water. It tells you how many people will not fit.

## This is a sketching tool

It knows nothing about real ground. It cannot see slopes, flooding, drainage, soil, landslide risk, access for trucks, or how people want to live and stay safe, such as lighting and the location of latrines for women and girls. Use it to compare ideas before a site visit, and never in place of a qualified site planner and the community.

## How it is tested

Each rule has cases on both sides of its limit. The auto layout must meet every rule on a site of the right size, keep every shelter reachable, respect unusable ground, and report people who do not fit.

## Limits

Square cells only, one person's plan at a time, and no maps or GPS. Distances are straight lines, not walking routes.

## Tests

```
python -m unittest discover -s tests
```

MIT licence.
