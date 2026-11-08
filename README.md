# Memory & Marvell Desk (GitHub Pages edition)

Single-file dashboard covering memory and storage stocks (Micron, SK hynix, Samsung, Sandisk, Western Digital, Kioxia, Seagate) and Marvell against its custom-silicon, connectivity and optics competitors (Broadcom, Astera Labs, Credo, NVIDIA, AMD, MediaTek, Alchip, Global Unichip, Lumentum, Coherent). Built and published by GitHub Actions with no dependency on Claude. Same pipeline as the IREN Markets Desk.

- Live page: https://aussie123456.github.io/memory-marvell/ (repo https://github.com/aussie123456/memory-marvell)
- Manual refresh: Actions tab > **Refresh dashboard** > **Run workflow**. The page's own **Refresh data** button opens that screen. Allow 3 to 5 minutes.
- Scheduled refresh: daily at 22:00 UTC (9:00am Sydney during daylight saving). See the cron note in `.github/workflows/refresh.yml` for the April DST change.

## Files

| File | Purpose |
|---|---|
| `template.html` | The page: layout, CSS, rendering JS and empty data blocks. Edit this to change the page. |
| `curated.json` | Hand-maintained data: memory-cycle tiles, latest results per name, Lumentum deal terms, Marvell Investor Day targets, bull case, bear case, what to watch, competitor positioning notes. Every item carries a source URL. |
| `build.py` | Builder (stdlib Python 3.8+): injects `curated.json`, repoints the Refresh button at the workflow, re-fetches every data block with a `data-url`, back-fills failed blocks from the previously published page, stamps `d-meta`, writes `dist/index.html`. |
| `tools/build-local.pl` | Perl mirror of the builder for a local preview on a machine without Python. Output is gitignored. |
| `.github/workflows/refresh.yml` | Builds and deploys to GitHub Pages on the schedule, on **Run workflow**, and on any push that changes the files above. |

## How data flows

Each `<script type="application/json" id="d-...">` block in the template carries a `data-url`. The builder re-fetches each URL (Yahoo Finance chart and quoteSummary with the cookie-and-crumb session, Yahoo FX for USD/KRW, USD/JPY and USD/TWD, Google News RSS) and rewrites the block. The page's JavaScript reads the blocks and renders everything client-side, so the published page needs no network access and no secrets.

If a feed fails, the builder keeps that block's payload from the page currently published on Pages (fetched at the start of the run), and `d-meta` records the error. The build fails, and nothing is published, only if no block has data at all.

## One-time setup

1. Create an empty repository on GitHub (public, unless the plan supports Pages on private repos).
2. Push this folder (`git remote add origin ...; git push -u origin main`).
3. Repo **Settings > Pages > Build and deployment > Source**: **GitHub Actions**.
4. Actions tab > **Refresh dashboard** > **Run workflow**.

## Updating curated data

Edit `curated.json`, commit and push; the push triggers a rebuild. Keys: `memory_cycle` (tiles + selloff note), `results` (per ticker key: label, reported, bullets, src), `deal`, `mrvl_targets`, `bull`, `bear`, `watch`, `competitor_notes`. Ticker keys are the short keys used in the page (`MU`, `SKH`, `SEC`, `SNDK`, `WDC`, `KIOXIA`, `STX`, `MRVL`, `AVGO`, `ALAB`, `CRDO`, `NVDA`, `AMD`, `MTK`, `ALCHIP`, `GUC`, `LITE`, `COHR`).

## Known gaps

- Kioxia and Seagate have Yahoo fundamentals only; no curated results yet.
- Yahoo Finance occasionally rate-limits data-centre IPs. The builder retries the crumb four times and each block three times, and back-fills from the previous page on failure.
