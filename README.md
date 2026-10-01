# Bob & Berry — NFC collar pages

A small static website so that anyone who finds Bob or Berry can identify the
dog and reach Roy within seconds. English and Hebrew, no accounts, no database,
no tracking.

| Address   | What it is                                   |
|-----------|----------------------------------------------|
| `/`       | Shared homepage (both dogs, contact buttons) |
| `/bob/`   | Bob's page — written to Bob's NFC tag        |
| `/berry/` | Berry's page — written to Berry's NFC tag    |

## What's in this folder

```
site.toml      ← THE ONE FILE TO EDIT: contacts, dog details, photos, all wording (EN + HE)
photos/        ← original photos (not published directly)
build.py       ← turns site.toml + photos into the website
public/        ← the finished website — this folder is what gets published
vercel.json    ← Vercel settings (serve public/, redirects, no-index headers)
nfc-kit/       ← appears once base_url is set: exact tag URLs + printable QR codes
src/           ← stylesheet and script (only for design changes)
tools/qr.py    ← QR code generator used by the build
```

Requirements: Python 3.11+ and Pillow (`python -m pip install pillow`, once).

## Everyday changes

1. Edit `site.toml` (any text editor — keep the quotes and braces).
2. Run `python build.py`. It checks everything and prints what is missing.
3. Commit and push to GitHub — Vercel and GitHub Pages update within a minute
   (see *Publishing*). The collar URLs never change.

To preview locally: `python -m http.server 8000 --directory public`, then open
<http://localhost:8000/bob/>.

**Change a phone number** — `[owner]` (Roy, shown as "Father") or `[backup]`
(Yana, shown as "Mother") → `phone`, `phone_display`, `whatsapp`.
Always international format (`+972-54-…`). Empty `whatsapp` hides the WhatsApp
buttons; empty `email` hides email.

**Change text** — dog facts live under each `[[dogs]]` block; interface wording
lives under `[ui]`. Every text is `{ en = "…", he = "…" }`. An empty optional
field simply disappears from the page.

**Change photos** — put the file in `photos/bob/` (or `photos/berry/`) and
add or edit a `[[dogs.photos]]` block: `file`, `alt` (a short description in
both languages) and optionally `focus` (which part stays visible in square-ish
crops, e.g. `"50% 40%"`). The **first** photo is the main portrait. The build
resizes each photo, makes WebP + JPEG versions, and strips all hidden metadata,
including GPS location.

**Never change a dog's `slug`** once tags are written — it *is* the collar URL.

## Publishing (stable public URLs)

The site lives in the GitHub repository `RockShepherd1409/bob-and-berry` and is
served from two places. **Every push to `main` updates both automatically:**

| Host | Address | Set up by |
|------|---------|-----------|
| **Vercel** (primary — on the tags) | `https://bob-and-berry.vercel.app/` | Vercel project `bob-and-berry`, connected to the repo; settings in `vercel.json` |
| GitHub Pages (mirror) | `https://rockshepherd1409.github.io/bob-and-berry/` | `.github/workflows/pages.yml` |

So the update routine is: edit `site.toml` → `python build.py` → commit → push.

Keep the addresses permanent:

- Don't rename or delete the Vercel project, the GitHub repository, or the
  GitHub account — the addresses depend on those names.
- Vercel also creates one-off addresses for every deployment
  (`bob-and-berry-xxxx-….vercel.app`). **Never** write those to a tag.
- The only address that survives switching hosts is your own domain
  (e.g. `bobandberry.co.il`, added under the Vercel project's *Domains*). If you
  add one later, keep the old addresses working and rewrite the tags only when
  convenient.

Don't enable Vercel Analytics or any other tracking — the page promises none.

## Writing the NFC tags

1. Set `base_url` in `site.toml` to the permanent address (no trailing slash),
   run `python build.py`, and open `nfc-kit/index.html`. It lists the exact URL
   for each tag (e.g. `https://…/bob/`) plus printable QR codes. The build
   refuses to make the kit from an empty, temporary or placeholder address.
2. Tag: NTAG213/215/216 (any is big enough), ideally a waterproof collar tag.
3. Write with a free app such as **NFC Tools** (iOS/Android): *Write → Add a
   record → URL/URI* → paste the URL → *Write* → hold the tag to the phone.
4. Test (see checklist). Locking the tag is optional and **permanent**.

Good to know: NFC only stores the link — it is not a GPS tracker, and scanning
does not tell you where the dog is. The finder needs mobile data for the first
visit. iPhone XS and newer read tags automatically with the screen on; older
iPhones use the NFC reader in Control Center; Android needs NFC switched on.
**Keep the phone number engraved on the physical tag as well.**

## Checklist before trusting the collars

Verified during development (local preview, Chrome engine, emulated phone sizes):

- [x] `/bob/` and `/berry/` open the right dog directly, including on refresh
      and with `?lang=he` / `?lang=en`.
- [x] Call + WhatsApp + number visible on the first screen at 375 × 667.
- [x] Every call / WhatsApp / SMS / email link uses the right number or address;
      messages name the right dog (both on the homepage) in both languages.
- [x] Hebrew RTL layout, English layout, language choice remembered,
      browser-language default, phone numbers stay left-to-right in Hebrew.
- [x] Lightbox: swipe/arrows/keyboard, counter, close, focus returns;
      broken photos show a neutral placeholder; contact still works.
- [x] No location requests and no tracking; no "sent" message is ever shown.
- [x] Missing essentials show a red preview banner and disabled buttons.
- [x] Works without JavaScript; 320 px wide; text enlarged to 200 %; keyboard.
- [x] Published photos contain no metadata; QR codes decode correctly.

Still needs a real phone (please do these yourself):

- [ ] Publish, then open both URLs over mobile data on an iPhone (Safari) and an
      Android phone (Chrome).
- [ ] On both: tap **Call**, **WhatsApp** (message pre-filled, you press Send),
      **SMS** (body pre-filled), **Email**, **Copy number**.
- [ ] Write the tags, scan each with both phones **while on the collar**
      (metal parts can weaken NFC), confirm the right dog opens.
- [ ] Scan the printed QR codes with a phone camera.
