# Odoo Blog to Email

An Odoo module that automatically refreshes an email mailing with your latest tagged blog posts whenever you publish. No scripts, no manual steps — publish a post and your mailing updates itself.

> **Multi-version:** branches `18.0` and `19.0` are available — install from the branch that matches your Odoo version.

---

## What it does

- Watches for blog posts published with a specific tag (default: `Newsletter`)
- When a matching post is published, fetches the N most recent posts with that tag
- Injects them as a styled Recent Posts section into a configured mailing
- All settings live in **Settings → Email Marketing** — no code required after install

---

## Requirements

- Odoo 18.0 or 19.0 (Community or Enterprise) — use the branch matching your version
- The following apps must be installed:
  - **Blog** (`website_blog`) — Odoo's website blog
  - **Email Marketing** (`mass_mailing`)

---

## Installation

### Option A — Odoo.sh

1. Copy the `odoo_blog_to_email/` folder into your Odoo.sh repository alongside your other custom modules:
   ```bash
   cp -r odoo_blog_to_email/ /path/to/your-odoo-sh-repo/
   ```
2. Commit and push to your Odoo.sh branch:
   ```bash
   git add odoo_blog_to_email/
   git commit -m "feat: add odoo_blog_to_email module"
   git push origin main
   ```
3. Wait for the Odoo.sh build to show **Test: Success**
4. Go to **Apps**, remove the "Installed" filter, search **"Odoo Blog to Email"**, click **Activate**

### Option B — Self-hosted Odoo

1. Copy `odoo_blog_to_email/` into your Odoo addons path
2. Restart the server with an update:
   ```bash
   ./odoo-bin -c your.conf -u odoo_blog_to_email
   ```
3. Go to **Apps**, search **"Odoo Blog to Email"**, click **Activate**

---

## What happens on install

When you activate the module, two things happen automatically:

1. A starter mailing called **"Recent Posts — Your Newsletter"** is created in **Email Marketing → Mailings** as a draft — with the Recent Posts block already in the body
2. **Settings → Email Marketing** is pre-configured to point at that mailing, and a daily scheduled action is created as a safety net

You only need to customise the mailing design and save your Settings. No manual block insertion required.

---

## Configuration

Go to **Settings → Email Marketing** and scroll to the **"Odoo Blog to Email"** section:

| Field | Default | Description |
|---|---|---|
| **Welcome mailing** | Starter mailing (auto-set on install) | The mailing to refresh when a post is published |
| **Blog tag** | `Newsletter` | Tag name to watch — case-insensitive |
| **Number of posts** | `3` | How many recent posts to inject |

Click **Save**.

---

## Customising the starter mailing

The starter mailing is a minimal template. To make it yours:

1. Go to **Email Marketing → Mailings** and open **"Recent Posts — Your Newsletter"**
2. Update the subject line
3. In the editor, replace the placeholder header with your logo or brand name
4. Update the intro copy
5. Leave the **Recent Posts** section in place — it will be populated automatically on the next publish

Each post in the Recent Posts section renders as:
- Numbered label (`01 · LATEST`, `02 · PREVIOUS`, `03 · EARLIER`)
- Post title (bold, linked)
- ~160-character excerpt (cleaned of dates, title echoes, and filler text)
- **Read →** link to the full post on your website

---

## Using an existing mailing instead of the starter

If you want the module to refresh a mailing you've already built:

1. Open the mailing in the editor and switch to **Code view** (the `</>` button in the toolbar)
2. Find the location in the HTML where you want the Recent Posts block to appear
3. Insert an empty anchor block there:
   ```html
   <div class="s_text_block o_mail_snippet_general" data-snippet="s_text_block" data-name="RecentPosts">
   </div>
   ```
4. Save the mailing
5. In **Settings → Email Marketing → Odoo Blog to Email**, set **Welcome mailing** to point at your mailing
6. Click **Save**

The module replaces that whole `data-name="RecentPosts"` element on each refresh. Everything outside it is never touched.

> Earlier versions anchored on `<!-- BLOG_POSTS_SLOT:START -->` / `:END` comments. The mail editor **strips HTML comments on save**, so those anchors vanished the first time anyone edited the mailing and the refresh silently stopped. Comment markers are still honoured once, and are replaced with the `data-name` block on that first refresh.

---

## How the refresh works

There is no refresh button, because there is nothing to press. The module re-renders whenever the answer could have changed:

- **On any blog post create, write or delete** that touches `is_published`, `tag_ids`, `name`, `teaser`, `post_date`, `blog_id` or `active`
- **Once a day**, via the `Blog to Email: refresh mailing` scheduled action — a safety net for anything that never passes through those hooks (a scheduled `post_date` coming due, a data import, a database restore)

Both paths call the same method, and that method **writes only when the rendered block differs from what the mailing already holds**. Firing it constantly is free, which is what lets it fire on everything rather than trying to detect the one transition that matters.

The mailing's `state` is never changed — it stays in draft.

**Post URLs** come from each post's own website domain (`get_base_url()`), not from `web.base.url`. On a hosted instance those differ: `web.base.url` is the `*.odoo.com` hostname while the website record carries the real domain.

### Seeing what it did

**Settings → Email Marketing → Odoo Blog to Email → Last refresh** shows the outcome of the most recent attempt, including the reason when it did nothing:

```
2026-09-07 18:22:04 UTC — refreshed 'Welcome to 19 Prince!' with 3 post(s)
2026-09-07 18:22:04 UTC — already current — 3 post(s)
2026-09-07 18:22:04 UTC — no RecentPosts block in mailing 23 ('Welcome to 19 Prince!')
```

---

## Testing

1. Go to **Blog** and publish, retitle or tag any post
2. Check **Settings → Email Marketing → Last refresh**
3. Open your configured mailing in Email Marketing — the Recent Posts section should show the current top N posts

> **Tip:** If the mailing is open in a browser tab when the refresh fires, close the tab and reopen the mailing. Saving from an open editor tab can overwrite the auto-refresh.

---

## Logging

Events are logged to the standard Odoo server log:

```
INFO  odoo_blog_to_email: refreshed 'Welcome to 19 Prince!' with 3 post(s)
INFO  odoo_blog_to_email: already current — 3 post(s)
WARN  odoo_blog_to_email: no mailing configured in Settings
WARN  odoo_blog_to_email: no RecentPosts block in mailing 23 ('Welcome to 19 Prince!')
WARN  odoo_blog_to_email: no published posts tagged 'newsletter'
```

---

## File structure

```
odoo_blog_to_email/
├── __init__.py                          # Module init + post_install hook
├── __manifest__.py                      # Module metadata and dependencies
├── data/
│   └── mailing_starter.xml              # Starter mailing created on install
├── models/
│   ├── __init__.py
│   ├── blog_post.py                     # write() hook + HTML rendering logic
│   └── res_config_settings.py          # Settings fields (mailing, tag, count)
└── views/
    └── res_config_settings_views.xml    # Settings UI panel
```

---

## License

LGPL-3 — free to use, modify, and distribute.

Built by [19 Prince](https://www.19prince.com) — Odoo-native growth strategy.
