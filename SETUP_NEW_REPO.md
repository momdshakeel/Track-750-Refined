# Launch a second app without touching your original

This guide uses the local folder you already have (`Track500-main`) as the starting point for a
**new** GitHub repository and a **new** Streamlit app. Your old repository and live Streamlit app
are not changed by anything in this folder.

---

## 1. Create the new GitHub repository

1. Log in to GitHub and click **New repository**.
2. Suggested name: `MarketPulse-750-Refined` (any name works).
3. Keep it **Public** if you want to deploy on Streamlit Community Cloud's free tier.
4. **Do not** initialise it with a README, `.gitignore`, or licence — we will push the files we already have.
5. Copy the repository URL, for example:
   `https://github.com/YOUR_USERNAME/MarketPulse-750-Refined.git`

---

## 2. Push this local folder to the new repository

Open a terminal in this folder (`C:\Users\CCI\Documents\Default Project\Track500-main`) and run:

```bash
git init
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/MarketPulse-750-Refined.git
git add .
git commit -m "Initial import with UI improvements"
git push -u origin main
```

**If you want to keep the old repository's commit history**, instead of `git init` do this in a
*separate new folder*:

```bash
git clone https://github.com/YOUR_USERNAME/OLD_REPO.git MarketPulse-750-Refined
cd MarketPulse-750-Refined
git remote rename origin old-origin
git remote add origin https://github.com/YOUR_USERNAME/MarketPulse-750-Refined.git
# copy the edited files from this folder into the new folder, then:
git add .
git commit -m "Import refined UI"
git push -u origin main
```

`old-origin` is only a backup reference. Never push to it. You can delete it later with
`git remote remove old-origin`.

---

## 3. Enable the daily and weekly jobs in the new repository

1. In the new repository go to **Settings → Actions → General → Workflow permissions**.
2. Select **Read and write permissions** and save. (The job commits `data/` back to the repo.)
3. Open the **Actions** tab → **Daily scan** → **Run workflow**.
4. Wait a few minutes. A `data/` folder with `latest.csv` (now including the `Darvas_*` and `VCP_Base_*` / `VCP_Box_*` columns),
   `meta.json`, `shares.csv`, and `data/history/` should appear after a successful run.
5. Open the **Actions** tab → **Weekly shortlist** → **Run workflow** once. This creates
   `data/weekly/weekly_shortlist.json` with the first top-20 snapshot. Afterwards it runs automatically every
   Sunday at 5 PM IST and keeps 13 lists.

Your old repository's Actions and data are completely separate.

---

## 4. Deploy the new Streamlit app

1. Go to <https://share.streamlit.io> → **New app**.
2. Choose the **new** repository, branch `main`, main file `app.py`.
3. Click **Deploy**.

### Data source (important)

The edited app is now **local-first**: it reads the `data/` folder committed to its own
repository. No configuration is needed for a fresh start.

If you want the app to pick up new scan data without waiting for a Streamlit redeploy, you can
optionally point it at the new repository's raw files:

- In Streamlit Cloud → your app → **Settings → Secrets**, add:

```toml
MARKETPULSE_DATA_URL = "https://raw.githubusercontent.com/YOUR_USERNAME/MarketPulse-750-Refined/main/data"
```

- Or set the environment variable `MARKETPULSE_DATA_URL` to the same URL when self-hosting.

Leave it unset to stay local-first. The old hard-coded `momdshakeel/Track500` URL has been removed.

---

## 5. What changed in this local copy

- **Full visual refresh:** new pulse-logo header card with cyan/violet gradients, redesigned KPI stat
  cards with icon badges and hover lift, capsule-style screen tabs, restyled status pills, meters,
  buttons and sidebar.
- **In-app light / dark switch:** the ☀️ / 🌙 control in the header recolours the entire app —
  including the sortable tables and chart dialogs — without using Streamlit's settings menu.
- **Faster charts:** chart history downloads are cached for 1 hour, so reopening a stock is instant.
  Chart default height reduced from 900 px to 760 px; theme sync interval reduced.
- **Better mobile layout:** all native multi-column rows stack on narrow screens, the header/tabs/
  view row keep their mobile-friendly behaviour, dialogs get tighter padding, pill rows scroll with
  snap, and iOS safe-area bottom padding is respected.
- **New UX:** a **Reset filters** button next to **Reload data** in the Filters panel.
- **New-repo ready:** data source is local-first and configurable; history snapshots also load locally.

Your original GitHub repository and live app are untouched by these local file edits.
