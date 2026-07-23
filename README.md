# mashrurkabir.com

Static portfolio site — plain HTML, CSS, and vanilla JavaScript. No build step, no backend. Built for GitHub Pages with the custom domain `mashrurkabir.com`.

## Folder structure

```
/
├── index.html        Home (hero, selected work, verification frontier, CTA)
├── about.html        Bio, What I Do, north stars
├── projects.html     Project card grid
├── mtk-news.html     MTK News case study — linked from the Projects grid and the home
│                     "Selected Work" card, deliberately NOT in the primary nav
├── jetlined.html     Jetlined case study — linked from the Projects grid and the home
│                     "Selected Work" card, deliberately NOT in the primary nav
├── writing.html      Article list — Proxima Report + Substack (coming soon)
├── contact.html      Formspree form + direct links
├── 404.html          On-brand not-found page (GitHub Pages serves this automatically)
├── style.css         All styles (design tokens at the top)
├── script.js         All behavior (hero toggle at the top)
├── favicon.svg       Star mark favicon
├── robots.txt        Crawler rules + sitemap pointer
├── sitemap.xml       Page list for search engines — add an entry when you add a page
├── CNAME             Custom-domain file for GitHub Pages — leave as-is
├── README.md         This file
├── data/
│   └── articles.json Auto-managed article ledger — every post the feeds have ever
│                     served (see "Auto-updating the writing page")
└── assets/
    ├── hero-poster.jpg   Placeholder poster (replace with a real video frame later)
    ├── hero.mp4          ← you add this (hero video)
    ├── hero.webm         ← optional WebM twin
    ├── portrait.jpg      ← you add this (about-page photo)
    └── og-image.jpg      ← optional 1200×630 social-share image
```

## Preview locally

From the project folder, run either:

```bash
python3 -m http.server 8000     # then open http://localhost:8000
```

or use the VS Code **Live Server** extension. Opening the HTML files directly (`file://`) mostly works, but a local server behaves exactly like the deployed site.

## Customization checklist

Every spot that needs your input is marked with a `TODO` comment. Search the project for **`TODO`** and work down the list. The big ones:

1. **Hero background** — see the next section.
2. **Formspree endpoint** — `contact.html`, the form's `action` attribute.
3. **Links** — social URLs in every footer, the email/LinkedIn/Proxima links on `contact.html`, article URLs on `writing.html`, and the Jetlined GitHub link on `jetlined.html`. (The MTK News and Jetlined cards link to their own subpages, `mtk-news.html` and `jetlined.html` — add an MTK News archive link on its page if one exists.) When you fill in LinkedIn / X, also add those URLs to the JSON-LD `sameAs` lists in `index.html` and `about.html`.
4. **Copy** — the About page is a draft written to be edited; make it yours.
5. **Photo** — swap the About placeholder for `assets/portrait.jpg` (instructions in the HTML comment).
6. **Accent color** — optional; change `--accent` at the top of `style.css`.

Note: the header and footer are plain shared markup, so a nav or footer edit means updating all six HTML files (plus `404.html` if relevant). Keep them identical. `mtk-news.html` intentionally has no `aria-current` in the nav — it's a subpage, not a nav destination.

## Site background: the starfield (and the hero video option)

The animated canvas starfield — slow upward drift, gentle twinkle — is the **site-wide background**. It renders into a fixed canvas at the top of `<body>` on every page (shared markup, like the header/footer), so it stays visible behind all content while scrolling. It pauses in background tabs and renders a static frame for users with reduced motion enabled.

The home hero can additionally paint a video over it. **One line** in `script.js` controls that:

```js
const HERO_BACKGROUND = 'starfield'; // 'starfield' | 'video'
```

- **`'starfield'` (current default)** — nothing extra; the hero is transparent and the site-wide starfield shows through. No assets needed; the site looks finished today.
- **`'video'`** — a full-bleed looping background video covers the starfield inside the hero only (the rest of the page keeps the starfield). Video bytes are never downloaded while starfield mode is selected (sources use `data-src`), so leaving the video markup in place costs nothing.

### Switching to video

1. Drop your loop into `assets/hero.mp4` (and optionally `assets/hero.webm`).
2. Replace `assets/hero-poster.jpg` with a real frame from the video (command below).
3. Flip the toggle in `script.js` to `'video'`.

If the file is missing or autoplay is blocked, the site falls back to the static poster automatically — nothing breaks.

### Recommended video specs

| Property | Target |
|---|---|
| Length | 10–15 s, seamless loop |
| Resolution | 1920×1080 (1280×720 is fine and ~half the weight) |
| Codec | H.264 MP4 (`yuv420p`), optional VP9 WebM twin |
| Frame rate | 24 fps |
| Audio | None — strip the audio track entirely |
| File size | **3–6 MB target, 8 MB hard ceiling** |

ffmpeg commands, from your source clip:

```bash
# MP4 (required)
ffmpeg -i source.mp4 -t 15 -an -vf "scale=1920:-2,fps=24" \
  -c:v libx264 -crf 28 -preset slow -pix_fmt yuv420p \
  -movflags +faststart assets/hero.mp4

# WebM (optional — better compression in Chrome/Firefox)
ffmpeg -i source.mp4 -t 15 -an -vf "scale=1920:-2,fps=24" \
  -c:v libvpx-vp9 -crf 38 -b:v 0 assets/hero.webm

# Poster from the first frame
ffmpeg -i assets/hero.mp4 -frames:v 1 -q:v 3 assets/hero-poster.jpg
```

If the MP4 lands over ~6 MB, raise `-crf` to 30 or drop to 720p. Dark, slow-moving footage (starfields, Earth from orbit, engine plumes at distance) compresses far better than fast bright motion.

## Formspree setup (contact form)

1. Create a free account at [formspree.io](https://formspree.io) and add a new form.
2. Copy the form ID from the endpoint it gives you (`https://formspree.io/f/mabcdxyz` → the ID is `mabcdxyz`).
3. In `contact.html`, replace `YOUR_FORM_ID` in the form's `action` attribute.

Until you do this, the form politely refuses to submit and tells visitors it isn't connected yet. The form works even with JavaScript disabled (plain POST); with JS it submits in-page and shows inline status. A hidden `_gotcha` honeypot field handles basic spam.

## Deploying to GitHub Pages with mashrurkabir.com

### 1. Push the site

```bash
git init
git add .
git commit -m "Launch portfolio site"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/mashrurkabir.com.git
git push -u origin main
```

(Any repo name works — `mashrurkabir.com` keeps it obvious.)

### 2. Enable Pages

Repo → **Settings → Pages** → Source: **Deploy from a branch** → Branch: `main`, folder `/ (root)` → Save. The site goes live at `https://YOUR_USERNAME.github.io/REPO_NAME/` within a minute or two.

### 3. Point the domain

At your registrar (Spaceship, Cloudflare, etc.), add these DNS records:

| Type | Name | Value |
|---|---|---|
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| CNAME | `www` | `YOUR_USERNAME.github.io` |

Notes:

- **Cloudflare users:** set these records to **DNS only** (gray cloud, not proxied) at least until GitHub issues the HTTPS certificate. You can experiment with proxying afterward, but DNS-only is the no-surprises configuration for Pages.
- These are GitHub's published Pages IPs; if anything acts up, double-check them against GitHub's current docs.

### 4. Connect it in GitHub

Repo → **Settings → Pages → Custom domain** → enter `mashrurkabir.com` → Save. GitHub runs a DNS check (can take a few minutes to a few hours after DNS changes propagate). Once it passes, tick **Enforce HTTPS**.

The `CNAME` file in this repo pins the domain so it survives future pushes — don't delete it. With the `www` CNAME record in place, `www.mashrurkabir.com` will redirect to the apex domain automatically.

### 5. Updating the site later

Just commit and push to `main` — Pages redeploys automatically in about a minute.

## Auto-updating the writing page

The article lists on `writing.html` refresh themselves from your RSS feeds — no manual editing. A scheduled GitHub Action fetches your latest posts and commits them back into the page, which triggers the normal Pages redeploy.

RSS feeds are windows, not archives — most platforms only serve the newest 10–20 items. So the script also keeps a **permanent ledger**, `data/articles.json`: every post it has ever seen is recorded there and never deleted, even after it falls out of the live feed. The featured lists show the newest 6 per source; everything older automatically collects in a compact **Archive** section at the bottom of the writing page (it appears only once there's something in it).

**Files involved:**

- `scripts/update_articles.py` — fetches the Proxima Report and Substack feeds, merges them into the ledger (append new, refresh existing, delete nothing), and rewrites the article regions of `writing.html`. Pure Python standard library, no dependencies.
- `data/articles.json` — the ledger. Auto-managed; committed by the Action so history survives across runs. To remove an article from the site, delete its entry here — but note the next run re-adds it if it's still in the live feed.
- `.github/workflows/update-articles.yml` — runs the script hourly (and on demand), committing only when something actually changed.
- `writing.html` — the article regions live between `<!-- ARTICLES:*:start -->` / `<!-- ARTICLES:*:end -->` comments (including the Archive block). **Don't hand-edit between those markers** — the script overwrites them. Everything else on the page is yours.

**How it behaves:**

- Features the newest 6 posts per source with your existing `.entry` styling; older pieces render as compact one-line archive rows (date, title, source), merged across sources, newest first.
- Substack has no posts yet, so it shows the "coming soon" panel automatically; it flips to a real list the moment you publish — no code change needed.
- If a feed is temporarily unreachable, that section is re-rendered from the ledger (identical output, so no commit — good content is never wiped), and the run aborts without writing anything only if *every* feed fails.

**One-time setup (after the repo is on GitHub):**

1. Push the site (see the deploy steps above). The workflow ships with `permissions: contents: write`, so its commits are allowed out of the box.
2. Repo → **Settings → Actions → General → Workflow permissions** → confirm **Read and write permissions** is selected (default for most accounts).
3. That's it. To trigger it immediately instead of waiting for the hour, go to the **Actions** tab → **Update articles** → **Run workflow**.

**Adjusting it:**

- Frequency: change the `cron` line in the workflow (e.g. `"0 */6 * * *"` for every 6 hours).
- How many posts are featured before the rest move to the Archive: `MAX_ITEMS` at the top of `scripts/update_articles.py`.
- Run it locally any time to preview: `python scripts/update_articles.py`.

Note: GitHub pauses scheduled workflows after ~60 days with no repo activity. The Action's own commits count as activity, so an actively-publishing site stays live; if it ever pauses, one manual run re-arms it.

## Performance notes

- The starfield costs effectively nothing: it caps device-pixel-ratio at 2, caps star count, sizes the canvas to the viewport (not the page), and stops animating when the tab is hidden.
- Keep the poster under ~300 KB and the video under 8 MB; those two files will dominate load time.
- Fonts load with `display=swap`, so text renders immediately.
- Everything else is a few KB of hand-written HTML/CSS/JS.

## Nice next steps (optional)

- Add `assets/og-image.jpg` (1200×630) and uncomment the `og:image` tag in each page's `<head>` for better link previews.
- Once the Substack launches, add the subscribe link and entries on `writing.html` (template is in the file).
- A real portrait and real article links will do more for the site than any further design work.
