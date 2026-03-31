# Workshop Plan — Accessing COG + STAC data from BCI
**Event:** Hyperspatial drone imagery to transform tropical forest science
**Location:** Gamboa, Panama — April 13–17, 2026
**Session:** Thursday 13:00–15:00

---

## At a glance

| Time | Segment | Format | Lead |
|------|---------|--------|------|
| Wed 08:20–08:30 | "STAC + COG: what is it, why should we care" | 10-min talk | Vincent |
| Thu 13:00–14:00 | Live demo: BCI COG + vegetation indices + QGIS | You drive | Vincent |
| Thu 14:00–15:00 | Hands-on exercises by language group | Participants run code | Vincent / Antoine / Ariane |

---

## Wednesday 08:20–08:30 — 10-min talk

### Slide 1 — The problem (2 min)
- BCI whole-island RGB drone mosaic = 50+ GB
- Old way: download everything, then look at it
- Analogy: downloading an entire encyclopedia to read one paragraph

### Slide 2 — What COG does (2 min)
- Tiled + overviewed internally → server sends only the tiles your viewport needs
- You read ~800 KB to get a chip from a 50 GB file
- The file stays on the server; you stream just what you see
- Works in QGIS, R (terra), Python (rasterio), ArcGIS — any GDAL-based tool

### Slide 3 — What STAC does (2 min)
- COG without a catalogue = a hard drive full of TIFs you can't search
- STAC = structured metadata: query by date, place, collection, resolution
- Our catalogue: `kanopia.org/stac-fastapi-pgstac/api/v1/pgstac/`

### Live demo (4 min)
1. Run `01_demo_bci_cog_indices.ipynb` (or show output already saved)
2. STAC query → list of BCI COG dates appears in 1 second
3. Pick dead tree tag 6949 → chip appears in ~2 seconds
4. "That was a 50 GB file. We just read 800 KB."

---

## Thursday 13:00–14:00 — Live demo (you drive, everyone watches)

### Tools
- `notebooks/01_demo_bci_cog_indices.ipynb` running on your laptop
- QGIS 3.44.3 with `qgis/load-bciwhole-rgb-cog-qgis-3.44.3.py`

### Flow

**13:00–13:10 — STAC query**
- Run cells 1–5: query STAC for `2024_bci`, show list of COGs by date
- Point out: dates span the whole 2024 growing season
- Show the raw STAC JSON in browser: `kanopia.org/stac-fastapi-pgstac/api/v1/pgstac/collections/2024_bci`

**13:10–13:25 — COG magic + vegetation indices**
- Run cells 6–11: pick dead tree 6949 from field GeoPackage
- Watch the 512×512 chip appear (~2 sec) → RGB view
- Compute GLI / VARI / GCC → side-by-side false-colour plot
- **The hook:** "Dead trees have low green index — watch them pop out in red"
- Two-date comparison: same tree, early 2024 vs late 2024 — GLI change visible

**13:25–13:40 — QGIS live demo**
- Switch to QGIS 3.44.3 (already open on your laptop)
- Open Python console → run `load-bciwhole-rgb-cog-qgis-3.44.3.py`
- Group `Dead_Tree_Evolution_80pct` appears with all dates
- Enable Temporal Controller → animate dates → dead tree visible across time
- **Network note:** COG reads are partial — only tiles in the viewport are fetched

**13:40–14:00 — Discussion**
- "What would you want to extract for your research?"
- Show how STAC query can be scoped by bbox, date range, collection keyword

---

## Thursday 14:00–15:00 — Hands-on exercises (split groups)

### Group setup

| Group | Notebook | Environment | Run where |
|-------|----------|-------------|-----------|
| Python | `02_exercises_python.ipynb` | Google Colab | Browser — share Colab link |
| R | `02_exercises_r.ipynb` | RStudio or Jupyter+IRkernel | Local laptop |
| QGIS (optional) | QGIS console script | QGIS 3.44.3 | Local (already installed only) |

### Workshop credentials (post on screen)
```
COG_USER = "panama"
COG_PASS = "panama123"
```
> Remove these credentials after the workshop ends.

### Exercises (Python + R both cover same 5 steps)

**Exercise 1** — Query STAC for `2024_bci`, print all item IDs and dates
**Exercise 2** — Pick one COG asset, open it with rasterio/terra, display RGB thumbnail
**Exercise 3** — Extract R, G, B arrays. Compute GLI. Plot as RdYlGn heatmap.
**Exercise 4** — Compute VARI and GCC. Compare all 3 indices in a 1×3 subplot.
**Exercise 5 (stretch)** — Extract chip for same point on 2 different dates. Compare GLI maps side by side.

---

## Risk mitigations

| Risk | Mitigation |
|------|-----------|
| Participant has no Gmail → can't open Colab | Pre-run notebooks with outputs saved → share as HTML |
| Network slow during COG reads | GDAL env vars: `GDAL_HTTP_TIMEOUT=120`, `GDAL_HTTP_MAX_RETRY=3` |
| R participants have no IRkernel | Copy-paste code into RStudio console; or use the `.R` script version |
| QGIS `pystac_client` missing in QGIS Python env | Pre-install in QGIS Python: `OSGeo4W Shell → pip install pystac-client` |
| Auth credentials leak after workshop | Remove `panama:panama123` after Thursday session ends |

---

## Files in this folder

```
workshop/
├── PLAN.md                              ← this file
├── requirements.txt                     ← Python packages
├── notebooks/
│   ├── 01_demo_bci_cog_indices.ipynb   ← Hour 1 live demo (you drive)
│   ├── 02_exercises_python.ipynb        ← Hour 2 Python group
│   └── 02_exercises_r.ipynb            ← Hour 2 R group
└── qgis/
    └── load-bciwhole-rgb-cog-qgis-3.44.3.py
```

The field datasheet GeoPackage (`2024-05-14_2024-06-11_fieldDatasheet.gpkg`) lives in
`../notebooks/` and is referenced by the demo notebook via relative path.
