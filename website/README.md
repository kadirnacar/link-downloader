# Link Downloader product website

Static product and documentation website intended for:

- https://ytdlp.bengsoft.com/

## Contents

- `index.html` — product overview, features, screenshot, downloads and repository links.
- `docs.html` — usage, system requirements, environment, build and architecture documentation.
- `styles.css` — responsive visual system, color palette and motion effects.
- `script.js` — mobile navigation and accessible reveal-on-scroll behavior.
- `assets/` — self-contained app icon and current source-package screenshot.
- `CNAME` — custom domain declaration for GitHub Pages, if selected.
- `sitemap.xml`, `robots.txt` — basic search indexing metadata.

## Publish

Publish the **contents** of this directory as the static website root. All visual assets are stored under `assets/`, so the website does not require files outside this directory.

The project package does not configure DNS, TLS, GitHub Pages, or the Bengsoft hosting account. Point `ytdlp.bengsoft.com` to the selected static host and enable HTTPS there. If GitHub Pages is used, the `CNAME` file declares the custom domain.

## External destinations

- Source: https://github.com/kadirnacar/link-downloader
- Releases: https://github.com/kadirnacar/link-downloader/releases
