# How to Build: Documentation Site (MkDocs)

**Date researched:** 2026-02-28  
**Difficulty:** Easy  
**Time required:** ~5 minutes

---

## Overview

The FLSUN-S1-Open-Source-Edition repository IS the documentation source. It uses **MkDocs** with the **Material for MkDocs** theme to generate a static documentation website deployed to GitHub Pages.

---

## What I Found

### GitHub Actions Workflow (`.github/workflows/docs.yml`)

The site is automatically built and deployed on every push to `main`:

```yaml
name: ci
on:
  push:
    branches:
      - main
permissions:
  contents: write
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Configure Git Credentials
        run: |
          git config user.name github-actions[bot]
          git config user.email 41898282+github-actions[bot]@users.noreply.github.com
      - uses: actions/setup-python@v5
        with:
          python-version: 3.x
      - run: pip install mkdocs-material
      - run: pip install mkdocs-glightbox
      - run: mkdocs gh-deploy --force
```

### Dependencies

| Package | Purpose |
|---|---|
| `mkdocs-material` | Material theme for MkDocs (includes MkDocs itself) |
| `mkdocs-glightbox` | Image lightbox plugin for zooming images |

### Local Build Steps

```bash
# 1. Clone the repository
git clone https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition.git
cd FLSUN-S1-Open-Source-Edition

# 2. Install Python dependencies
pip install mkdocs-material mkdocs-glightbox

# 3. Serve locally (hot-reload development server)
mkdocs serve
# → Opens at http://127.0.0.1:8000

# 4. Build static site (output to site/ directory)
mkdocs build
```

### MkDocs Configuration (`mkdocs.yml`)

Key settings from the config:

- **Theme:** `material` with light/dark mode toggle
- **Plugins:** `search`, `glightbox` (for image zoom)
- **Extra CSS:** custom styling + glightbox CSS
- **Extra JS:** glightbox JS + external links script
- **Markdown extensions:** admonitions, code highlighting, emoji, tables, superfences
- **Navigation:** Organized into sections: PREREQUISITES, PREPARATION, CONFIGURATIONS, EXTRAS, ADVANCED USERS, STL FILES

---

## Thoughts & Notes

- The build process for the docs is straightforward — standard MkDocs Material setup
- No special build system or Docker required
- The `docs/assets/downloads/` folder hosts firmware binaries and tools directly on the docs site (served via GitHub Pages)
- The glightbox plugin provides nice image zoom functionality for the step-by-step screenshots
- Fork-friendly: anyone can fork, modify docs, and deploy their own version
