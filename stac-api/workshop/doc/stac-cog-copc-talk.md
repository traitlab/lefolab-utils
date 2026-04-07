---
marp: true
theme: default
paginate: true
style: |
  section {
    font-family: 'Segoe UI', sans-serif;
    font-size: 1.6rem;
  }
  h1 { color: #2e7d32; }
  h2 { color: #388e3c; border-bottom: 2px solid #a5d6a7; padding-bottom: 0.2em; }
  .highlight { color: #2e7d32; font-weight: bold; }
  .muted { color: #757575; font-size: 1.2rem; }
---

# Accessing Drone Data
## STAC + COG / COPC
### What is it — why should we care

Vincent Le Falher · ForestGEO/STRI Gamboa · April 2026

---

## The problem in one number

> **BCI whole-island RGB drone mosaic = 50 GB per date — 17+ dates available**

Old workflow:
1. Download the whole file *(hours)*
2. Open it locally *(runs out of RAM)*
3. Look at 0.01 % of it
4. Repeat for every date

**This does not scale** — the BCI archive alone is over 750 GB.
The full COG/COPC collection across all sites is **> 13 TB and counting**.

---

## Where do these formats come from?

| Format | Born | Who | Status |
|--------|------|-----|--------|
| **COG** | 2016 | Open-source geo community (Planet Labs, GDAL team, AWS) | **OGC Community Standard** since 2023 |
| **COPC** | 2021 | Hobu Inc. + PDAL contributors | Open spec, built on LAZ/LASzip |
| **STAC** | 2017 | Radiant Earth + cloud providers (AWS, Microsoft, Google) | **OGC Community Standard** since 2021 |

**Why trust them?**
- GDAL supports all three → works in every GIS tool you already use
- Adopted by NASA Earthdata, ESA Copernicus, Microsoft Planetary Computer, Google Earth Engine
- Open specifications — no vendor lock-in, no licence fees

---

## What if the file stayed on the server?

Like **streaming a movie**: you don't download the whole film before watching the first frame.

```
Your laptop  ──►  "give me tiles for this bounding box"  ──►  server
             ◄──  ~800 KB                                ◄──
```

> You read **~800 KB** from a **50 GB** file.

That is exactly what **COG** and **COPC** enable.

---

## COG — Cloud Optimized GeoTIFF

A regular GeoTIFF reorganised so that:

| Feature | What it means |
|---------|---------------|
| **Internal tiling** | Data split into small spatial blocks |
| **Overviews baked in** | Zoom-out views pre-computed at multiple resolutions |
| **HTTP Range requests** | Client asks only for the bytes it needs |

**Result:** open a 50 GB file, read a 512 × 512 chip → **~800 KB transferred**

Works in QGIS, R (terra), Python (rasterio), ArcGIS — any GDAL-based tool.

---

## COPC — Cloud Optimized Point Cloud

Same idea, but for **LiDAR / photogrammetry point clouds**.

| | Regular LAZ | COPC |
|--|------------|------|
| Access pattern | Download everything, then filter | Spatial index baked in — stream only needed points |
| Per-tree extraction | Download full flight first | Stream bounding box directly |
| Pan & zoom over HTTP | Not possible | Native |

Works in PDAL, Python, QGIS — same GDAL-based ecosystem.

---

## STAC — SpatioTemporal Asset Catalog

COG/COPC without a catalogue = a hard drive full of files you can't search.

**STAC** adds structured, queryable metadata for every file:
- Date and time of acquisition
- Bounding box / footprint
- Collection name, sensor, resolution
- Direct link to the COG or COPC asset

**Query by date, place, collection** — results in under a second.
No login, no download, no local storage needed.

---

## Our setup at BCI

| Layer | What |
|-------|------|
| **STAC catalogue** | All BCI collections indexed and queryable |
| **COG files** | Hosted on Etienne's NAS — HTTP range requests enabled |
| **Collections** | bciwhole (17+ dates), 50ha plot, research plots, tower sites, … |
| **Total archive** | > 13 TB COG + COPC across all sites |

**BCI whole-island collection:**
- 17+ dates spanning 2024–2025
- ~47–54 GB per date
- **> 750 GB total** — streamed on demand, never downloaded in full

---

## Why downloading is not an option

Gamboa network speeds (measured April 2026):

| Location | Speed | Time to download one 50 GB COG |
|----------|------:|-------------------------------:|
| SI-internal Gamboa Lab | 19.4 Mbps | ~6h |
| STRI Camino de Cruces | 25.1 Mbps | ~4h 50m |
| GAMBOA RF Las Jacarandas | 36.7 Mbps | ~3h 20m |
| GAMBOA RF Camino de Cruces | 4.7 Mbps | ~24h |

With COG streaming → same query, any network: **~2 seconds**

---

## Why this matters for your research

| Before | Now |
|--------|-----|
| Email someone for a file | Query the catalogue yourself |
| Download 50 GB, run out of disk | Stream only the patch you need |
| "I don't know what dates are available" | Search by date range in one step |
| QGIS crashes opening the full mosaic | Load as COG — only fetches visible tiles |
| Wait hours on Gamboa wifi | 2-second chip, any connection |

**Drone data becomes as easy to access as Sentinel or Landsat.**

---

## This week

| When | What |
|------|------|
| **Today (10 min)** | This talk — concepts |
| **Thu 13:00–14:00** | Live demo: BCI COG chips, vegetation indices, QGIS temporal animation |
| **Thu 14:00–15:00** | Hands-on: Python / R / QGIS — you run the code |

**Catalogue:** kanopia.org/stac-fastapi-pgstac/api/v1/pgstac/

**Workshop access — User:** panama · **Password:** panama123

Questions? Let's go.
