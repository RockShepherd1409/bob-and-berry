#!/usr/bin/env python3
"""Build the Bob & Berry website from site.toml.

    python build.py            build public/  (and nfc-kit/ once base_url is set)
    python build.py --check    only check site.toml and list anything missing

Needs Python 3.11+ and Pillow (`pip install pillow`) for the photos.
Everything else is the standard library.

Output (upload the whole public/ folder to the host):
    public/index.html          shared homepage            → /
    public/<slug>/index.html   one page per dog           → /bob/  /berry/
    public/404.html            "not found" page that still shows the contact buttons
    public/photos/…            resized photos, all metadata (incl. GPS) removed
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import io
import json
import re
import shutil
import sys
import tomllib
from pathlib import Path
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.qr import qr_svg  # noqa: E402

SRC = ROOT / "src"
PHOTOS = ROOT / "photos"
OUT = ROOT / "public"
KIT = ROOT / "nfc-kit"
LANGS = ("en", "he")
WIDTHS = (480, 960, 1440)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
PLACEHOLDER_PHOTO = {"en": "Placeholder — add a photo of {n} in site.toml", "he": "מקום לתמונה של {n}"}
PLACEHOLDER_HOSTS = ("example.", "localhost", "127.0.0.1", "your-domain", "yourdomain", "claude.ai", "ngrok", "trycloudflare")


# ═══════════════════════════════════════════════════════════════ icons
_STROKE = {
    "phone": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "sms": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "mail": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/>',
    "copy": '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "left": '<path d="m15 18-6-6 6-6"/>',
    "right": '<path d="m9 18 6-6-6-6"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    "home": '<path d="m3 10 9-7 9 7v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
}
_FILL = {
    "whatsapp": '<path d="M17.47 14.38c-.3-.15-1.76-.87-2.03-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.94 1.16-.17.2-.35.22-.64.07-.3-.15-1.26-.46-2.39-1.47-.88-.79-1.48-1.76-1.65-2.06-.17-.3-.02-.46.13-.6.13-.14.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.03-.52-.07-.15-.67-1.61-.92-2.2-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.79.37-.27.3-1.04 1.02-1.04 2.48s1.07 2.88 1.21 3.07c.15.2 2.1 3.2 5.08 4.49.71.31 1.26.49 1.7.63.71.23 1.36.2 1.87.12.57-.09 1.76-.72 2-1.41.25-.7.25-1.29.18-1.41-.08-.13-.28-.2-.57-.35zM12.05 21.79h-.01a9.87 9.87 0 0 1-5.03-1.38l-.36-.21-3.74.98 1-3.65-.24-.37a9.86 9.86 0 0 1-1.51-5.26c0-5.45 4.44-9.88 9.89-9.88 2.64 0 5.12 1.03 6.99 2.9a9.83 9.83 0 0 1 2.89 7c0 5.45-4.44 9.88-9.88 9.88zm8.41-18.3A11.82 11.82 0 0 0 12.05 0C5.5 0 .16 5.34.16 11.89c0 2.1.55 4.14 1.59 5.95L.06 24l6.31-1.65a11.88 11.88 0 0 0 5.68 1.45h.01c6.55 0 11.89-5.34 11.89-11.89 0-3.18-1.24-6.16-3.49-8.41z"/>',
    "paw": '<ellipse cx="5.5" cy="10" rx="2.1" ry="2.7"/><ellipse cx="9.5" cy="5.6" rx="2.1" ry="2.8"/><ellipse cx="14.5" cy="5.6" rx="2.1" ry="2.8"/><ellipse cx="18.5" cy="10" rx="2.1" ry="2.7"/><path d="M12 11.5c-3 0-6.5 4.1-6.5 6.9 0 1.9 1.4 2.9 3.1 2.9 1.4 0 2.2-.8 3.4-.8s2 .8 3.4.8c1.7 0 3.1-1 3.1-2.9 0-2.8-3.5-6.9-6.5-6.9z"/>',
    "heart": '<path d="M12 21.35 10.55 20C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54z"/>',
}
_FLAGS = {
    "en": '<symbol id="f-en" viewBox="0 0 60 30" preserveAspectRatio="xMidYMid slice"><rect width="60" height="30" fill="#012169"/><path d="M0 0 60 30M60 0 0 30" stroke="#fff" stroke-width="6"/><path d="M0 0 60 30M60 0 0 30" stroke="#C8102E" stroke-width="2.4"/><path d="M30 0v30M0 15h60" stroke="#fff" stroke-width="10"/><path d="M30 0v30M0 15h60" stroke="#C8102E" stroke-width="6"/></symbol>',
    "he": '<symbol id="f-he" viewBox="0 0 220 160" preserveAspectRatio="xMidYMid slice"><rect width="220" height="160" fill="#fff"/><rect y="15" width="220" height="25" fill="#0038b8"/><rect y="120" width="220" height="25" fill="#0038b8"/><path d="M110 50 136 95H84ZM110 110 84 65h52Z" fill="none" stroke="#0038b8" stroke-width="5.5"/></symbol>',
}


def sprite():
    s = ['<svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true">']
    for k, v in _STROKE.items():
        s.append(f'<symbol id="i-{k}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
                 f'stroke-linecap="round" stroke-linejoin="round">{v}</symbol>')
    for k, v in _FILL.items():
        s.append(f'<symbol id="i-{k}" viewBox="0 0 24 24" fill="currentColor">{v}</symbol>')
    s += _FLAGS.values()
    s.append("</svg>")
    return "".join(s)


def icon(name, cls=""):
    return f'<svg class="icon {cls}" aria-hidden="true" focusable="false"><use href="#i-{name}"/></svg>'


def flag(lang):
    return f'<svg class="flag" aria-hidden="true" focusable="false"><use href="#f-{lang}"/></svg>'


FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="16" fill="#2b6a62"/>'
           f'<g fill="#fff" transform="translate(8 7) scale(2)">{_FILL["paw"]}</g></svg>')


# ═══════════════════════════════════════════════ inline scripts (tiny)
# Runs in <head> before anything is drawn: picks the language so Hebrew
# visitors never see a flash of English.  ?lang= > saved choice > browser.
HEAD_JS = (
    "(function(d){var h=d.documentElement,l;h.classList.add('js');"
    "try{var p=new URLSearchParams(location.search).get('lang');if(p==='he'||p==='en')l=p}catch(e){}"
    "if(!l){try{var s=localStorage.getItem('bb-lang');if(s==='he'||s==='en')l=s}catch(e){}}"
    "if(!l){var n=(navigator.languages&&navigator.languages[0])||navigator.language||'';l=/^(he|iw)\\b/i.test(n)?'he':'en'}"
    "h.lang=l;h.dir=l==='he'?'rtl':'ltr'})(document);"
)

# Runs at the end of <body>: swaps in the chosen language, keeps the age
# current, and shows the sticky contact bar once the main buttons scroll away.
APPLY_JS = """(function(){var H=document.documentElement,D=JSON.parse(document.getElementById('bb-i18n').textContent);
function t(k,l){var v=D[k];return v?v[l||(H.lang==='he'?'he':'en')]:''}
function age(l){var e=document.getElementById('bb-age');if(!e)return;var b=e.getAttribute('data-born').split('-'),n=new Date(),m=n.getMonth()+1,y=n.getFullYear()-(+b[0]);
if(m<+b[1]||(m===+b[1]&&n.getDate()<+b[2]))y--;if(y<1)return;e.textContent=t(y===1?'age_1':y===2?'age_2':'age_n',l).split('{n}').join(y)+' ('+t('born_on',l)+')'}
function apply(l){var i,j,e,p,q,a;H.lang=l;H.dir=l==='he'?'rtl':'ltr';
a=document.querySelectorAll('[data-i]');for(i=0;i<a.length;i++){e=a[i];q=D[e.getAttribute('data-i')];if(q)e.textContent=q[l]}
a=document.querySelectorAll('[data-ia]');for(i=0;i<a.length;i++){e=a[i];p=e.getAttribute('data-ia').split('|');for(j=0;j<p.length;j++){q=p[j].split('=');if(D[q[1]])e.setAttribute(q[0],D[q[1]][l])}}
a=document.querySelectorAll('.lang a');for(i=0;i<a.length;i++){if(a[i].getAttribute('data-lang')===l)a[i].setAttribute('aria-current','true');else a[i].removeAttribute('aria-current')}
if(D.title)document.title=D.title[l];age(l)}
window.BB={D:D,t:t,apply:apply};
if(H.lang==='he')apply('he');else age('en');
var bar=document.querySelector('.sticky-bar'),act=document.getElementById('contact-actions');
if(bar){if(act&&'IntersectionObserver' in window){new IntersectionObserver(function(x){bar.classList.toggle('is-shown',!x[0].isIntersecting)}).observe(act)}else{bar.classList.add('is-shown')}}
})();"""


# ═══════════════════════════════════════════════════════════ helpers
def esc(s):
    return html.escape(str(s), quote=True)


def pair(v):
    """Normalise a config value to {'en': …, 'he': …} — or None when empty."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        v = str(v)
    if isinstance(v, str):
        v = v.strip()
        return {"en": v, "he": v} if v else None
    en, he = str(v.get("en", "")).strip(), str(v.get("he", "")).strip()
    if not en and not he:
        return None
    out = {"en": en or he, "he": he or en}
    if str(v.get("he_f", "")).strip():
        out["he_f"] = str(v["he_f"]).strip()
    return out


def fill(tpl, fem=False, **values):
    """Fill {placeholders} in a bilingual template. Values may be bilingual too."""
    out = {}
    for lang in LANGS:
        s = tpl["he_f"] if (lang == "he" and fem and tpl.get("he_f")) else tpl[lang]
        for k, v in values.items():
            s = s.replace("{%s}" % k, v[lang] if isinstance(v, dict) else str(v))
        out[lang] = s
    return out


def join(*pairs, sep=" "):
    return {lang: sep.join(p[lang] for p in pairs if p) for lang in LANGS}


def split_on(tpl, key, value):
    """Split a template around {key} → (before, value, after) so the value can be styled."""
    before, after = {}, {}
    for lang in LANGS:
        b, _, a = tpl[lang].partition("{%s}" % key)
        before[lang], after[lang] = b, a
    return before, value, after


def digits_of(raw):
    return re.sub(r"\D", "", raw or "")


def intl_display(d):
    if d.startswith("972") and len(d) == 12:
        return f"+972 {d[3:5]}-{d[5:8]}-{d[8:]}"
    return "+" + d


def local_display(d):
    if d.startswith("972") and len(d) == 12:
        return f"0{d[3:5]}-{d[5:8]}-{d[8:]}"
    return intl_display(d)


def tint(hex_color, amount=0.13):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(255 - (255 - c) * amount) for c in (r, g, b))


def file_hash(path, n=10):
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()[:n]


def tel_url(d):
    return f"tel:+{d}"


def wa_url(d, text):
    return f"https://wa.me/{d}?text={quote(text, safe='')}"


def sms_url(d, text):
    # "?&body=" is understood by both iOS Messages and Android.
    return f"sms:+{d}?&body={quote(text, safe='')}"


def mail_url(addr, subject, body):
    return f"mailto:{addr}?subject={quote(subject, safe='')}&body={quote(body, safe='')}"


class Report:
    def __init__(self):
        self.missing, self.warnings, self.done = [], [], []


# ═══════════════════════════════════════════════════════ config model
def load_config(rep):
    # utf-8-sig: tolerate the invisible "BOM" that Notepad/PowerShell may add
    text = (ROOT / "site.toml").read_text(encoding="utf-8-sig")
    try:
        cfg = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"\nsite.toml has a typo: {e}\n"
                 'Check for a missing quote, comma or brace near that line. Text values look like  { en = "…", he = "…" }')

    ui = {}
    for k, v in cfg.get("ui", {}).items():
        p = pair(v)
        if not p:
            continue
        if isinstance(v, dict) and (not str(v.get("en", "")).strip() or not str(v.get("he", "")).strip()):
            rep.warnings.append(f"[ui] {k}: a language is missing, the other one is used")
        ui[k] = p

    site = cfg.get("site", {})
    base = str(site.get("base_url", "")).strip().rstrip("/")
    m = {
        "ui": ui,
        "name": pair(site.get("name")) or {"en": "Bob & Berry", "he": "בוב וברי"},
        "base_url": base,
        "base_path": (urlparse(base).path.rstrip("/") + "/") if base else "/",
        "owner": contact(cfg.get("owner"), "owner", rep, required=True),
        "backup": contact(cfg.get("backup"), "backup", rep, required=False),
        "dogs": [],
    }
    if not m["owner"]:
        rep.missing.append("[owner] section")
        m["owner"] = contact({"name": {"en": "Owner", "he": "הבעלים"}}, "owner", Report(), required=True)
    if not m["owner"]["short"]:
        m["owner"]["short"] = m["owner"]["name"] = {"en": "the owner", "he": "הבעלים"}

    seen = set()
    for d in cfg.get("dogs", []):
        dog = dog_model(d, rep)
        if dog["slug"] in seen:
            rep.missing.append(f"two dogs use the slug '{dog['slug']}'")
        seen.add(dog["slug"])
        m["dogs"].append(dog)
    if not m["dogs"]:
        rep.missing.append("at least one [[dogs]] entry")
    return m


def contact(c, where, rep, required):
    if not c:
        return None
    name = pair(c.get("name"))
    short = pair(c.get("short_name")) or name
    tel = digits_of(c.get("phone"))
    raw = str(c.get("phone", "")).strip()
    if raw and (not raw.startswith("+") or len(tel) < 8):
        rep.missing.append(f"[{where}] phone '{raw}' must be in international format, e.g. +972-54-1234567")
        tel = ""
    if required and not tel:
        rep.missing.append(f"[{where}] phone")
    if required and not short:
        rep.missing.append(f"[{where}] short_name")
    wa_raw = str(c.get("whatsapp", "")).strip()
    wa = digits_of(wa_raw)
    if wa_raw and (not wa_raw.startswith("+") or len(wa) < 8):
        rep.missing.append(f"[{where}] whatsapp '{wa_raw}' must be in international format")
        wa = ""
    email = str(c.get("email", "")).strip()
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        rep.warnings.append(f"[{where}] email '{email}' doesn't look right — hidden")
        email = ""
    if not required and not (tel or email):
        rep.warnings.append(f"[{where}] has no phone or email — hidden")
        return None
    return {
        "name": name or short, "short": short or name,
        "fem": str(c.get("gender", "m")).lower().startswith("f"),
        "tel": tel, "wa": wa, "email": email,
        "disp": str(c.get("phone_display", "")).strip() or (local_display(tel) if tel else ""),
        "intl": intl_display(tel) if tel else "",
        "area": pair(c.get("home_area")),
    }


def dog_model(d, rep):
    slug = str(d.get("slug", "")).strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        rep.missing.append(f"dog slug '{slug}' (use lowercase letters, digits, dashes)")
        slug = slug or "dog"
    name = pair(d.get("name"))
    if not name:
        rep.missing.append(f"[{slug}] name")
        name = {"en": slug.title(), "he": slug}
    elif not str((d.get("name") or {}).get("he", "")).strip():
        rep.warnings.append(f"[{slug}] Hebrew name missing")
    accent = str(d.get("accent", "")).strip()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        accent = "#2b6a62"
    born = d.get("born")
    if born and not isinstance(born, dt.date):
        try:
            born = dt.date.fromisoformat(str(born).strip())
        except ValueError:
            rep.warnings.append(f"[{slug}] born '{born}' is not YYYY-MM-DD — age hidden")
            born = None
    photos = []
    for p in d.get("photos", []):
        f = str(p.get("file", "")).strip()
        src = PHOTOS / f
        if not f or not src.is_file():
            rep.warnings.append(f"[{slug}] photo not found: photos/{f} — skipped")
            continue
        photos.append({"src": src, "alt": pair(p.get("alt")) or name, "focus": str(p.get("focus", "")).strip() or "50% 50%"})
    if not photos:
        rep.missing.append(f"[{slug}] at least one photo (main portrait)")
    elif len(photos) < 4:
        rep.warnings.append(f"[{slug}] only {len(photos)} photo(s) — 4–5 work best")
    weight = d.get("weight_kg")
    return {
        "slug": slug, "name": name, "fem": str(d.get("sex", "")).lower() == "female",
        "sex": str(d.get("sex", "")).lower(), "accent": accent, "accent_soft": tint(accent), "born": born,
        "breed": pair(d.get("breed")), "size": pair(d.get("size")),
        "weight": weight if isinstance(weight, (int, float)) and weight > 0 else None,
        "coat": pair(d.get("coat")), "markings": pair(d.get("markings")),
        "temperament": pair(d.get("temperament")), "with_dogs": pair(d.get("with_dogs")),
        "with_animals": pair(d.get("with_animals")), "medical": pair(d.get("medical")),
        "alerts": [a for a in (pair(x) for x in d.get("alerts", [])) if a],
        "photos": photos,
    }


# ═══════════════════════════════════════════════════════════ photos
def process_photos(model, rep):
    try:
        from PIL import Image, ImageCms, ImageOps
    except ImportError:
        sys.exit("Pillow is needed for the photos. Install it once with:  python -m pip install pillow")

    keep = set()
    count = 0
    for dog in model["dogs"]:
        outdir = OUT / "photos" / dog["slug"]
        outdir.mkdir(parents=True, exist_ok=True)
        for ph in dog["photos"]:
            src = ph["src"]
            stem = re.sub(r"[^a-z0-9-]+", "-", src.stem.lower()).strip("-") or "photo"
            h = file_hash(src, 6)
            with Image.open(src) as im:
                im = ImageOps.exif_transpose(im)
                icc = im.info.get("icc_profile")
                if icc:
                    try:  # convert to plain sRGB so colours survive dropping the profile
                        im = ImageCms.profileToProfile(im, ImageCms.ImageCmsProfile(io.BytesIO(icc)),
                                                       ImageCms.createProfile("sRGB"), outputMode="RGB")
                    except Exception:
                        pass
                im = im.convert("RGB")
                W, Hh = im.size
                variants = []
                for target in WIDTHS:
                    w = min(target, W)
                    if variants and variants[-1]["w"] == w:
                        break
                    hgt = round(Hh * w / W)
                    base = f"{stem}-{h}-{w}"
                    jpg, webp = outdir / f"{base}.jpg", outdir / f"{base}.webp"
                    if not (jpg.exists() and webp.exists()):
                        small = im.resize((w, hgt), Image.Resampling.LANCZOS) if w != W else im
                        # Saving without exif=/xmp= drops ALL metadata, including GPS.
                        small.save(jpg, "JPEG", quality=80, optimize=True, progressive=True)
                        small.save(webp, "WEBP", quality=78, method=6)
                    keep.update({jpg.resolve(), webp.resolve()})
                    variants.append({"w": w, "h": hgt,
                                     "jpg": f"photos/{dog['slug']}/{base}.jpg",
                                     "webp": f"photos/{dog['slug']}/{base}.webp"})
                    if target >= W:
                        break
            ph["variants"] = variants
            count += 1
    # remove outputs of photos that are no longer listed
    for f in (OUT / "photos").rglob("*"):
        if f.is_file() and f.resolve() not in keep:
            f.unlink()
    for dpath in sorted((OUT / "photos").glob("*"), reverse=True):
        if dpath.is_dir() and not any(dpath.iterdir()):
            dpath.rmdir()
    rep.done.append(f"{count} photos resized (JPEG + WebP), all metadata removed")


# ═══════════════════════════════════════════════════════════ page kit
class Page:
    """Collects the bilingual strings a page uses. English is written into
    the HTML; the inline script swaps in Hebrew from the JSON table."""

    def __init__(self, model, prefix):
        self.m, self.ui, self.P = model, model["ui"], prefix
        self.d, self._rev = {}, {}

    def key(self, p, name=None):
        if name:
            self.d[name] = {"en": p["en"], "he": p["he"]}
            return name
        sig = (p["en"], p["he"])
        if sig not in self._rev:
            self._rev[sig] = k = f"s{len(self._rev)}"
            self.d[k] = {"en": p["en"], "he": p["he"]}
        return self._rev[sig]

    def u(self, k, fem=False, **values):
        return fill(self.ui[k], fem=fem, **values)

    def tx(self, p, tag="span", cls="", extra=""):
        c = f' class="{cls}"' if cls else ""
        return f'<{tag}{c}{extra} data-i="{self.key(p)}">{esc(p["en"])}</{tag}>'

    def at(self, **attrs):
        shown, keys = [], []
        for n, p in attrs.items():
            n = n.replace("_", "-")
            shown.append(f'{n}="{esc(p["en"])}"')
            keys.append(f"{n}={self.key(p)}")
        return " " + " ".join(shown) + f' data-ia="{"|".join(keys)}"'

    def expose(self, *names, fem=False):
        """Make ui strings available to app.js under their own names."""
        for n in names:
            self.key(self.u(n, fem=fem), n)


def picture(pg, ph, sizes, eager=False, alt=True):
    vs = ph["variants"]
    P = pg.P
    webp = ", ".join(f"{P}{v['webp']} {v['w']}w" for v in vs)
    jpg = ", ".join(f"{P}{v['jpg']} {v['w']}w" for v in vs)
    fallback = P + vs[min(1, len(vs) - 1)]["jpg"]
    big = vs[-1]
    load = 'fetchpriority="high"' if eager else 'loading="lazy"'
    alt_attr = pg.at(alt=ph["alt"]) if alt else ' alt=""'
    return (f'<picture><source type="image/webp" srcset="{webp}" sizes="{sizes}">'
            f'<img src="{fallback}" srcset="{jpg}" sizes="{sizes}" width="{big["w"]}" height="{big["h"]}"'
            f'{alt_attr} {load} decoding="async" style="object-position:{esc(ph["focus"])}" data-ph></picture>')


def fallback_span(pg, text=None):
    return f'<span class="ph-fallback">{icon("paw")}{pg.tx(text or pg.u("photo_missing"))}</span>'


def lang_switch(pg):
    return (f'<nav class="lang"{pg.at(aria_label=pg.u("language"))}>'
            f'<a href="?lang=en" data-lang="en" lang="en" hreflang="en" aria-current="true">{flag("en")}English</a>'
            f'<a href="?lang=he" data-lang="he" lang="he" hreflang="he">{flag("he")}עברית</a></nav>')


def topbar(pg, home_href):
    name = pg.m["name"]
    return (f'<header class="topbar wrap"><a class="brand" href="{home_href}"{pg.at(aria_label=pg.u("home_link"))}>'
            f'{icon("paw")}{pg.tx(name, cls="brand-text")}</a>{lang_switch(pg)}</header>')


def message(pg, c, names):
    """The editable default message: 'Hi Roy, I found Bob. I'm at [..]. Please contact me.'"""
    return join(pg.u("msg_found", to=c["short"], name=names), pg.u("msg_where_blank"), pg.u("msg_contact_me", fem=c["fem"]))


def link_button(pg, c, *, href, icon_name, label, cls, aria=None, new_tab=False):
    """<a> whose href and (optionally) aria-label switch with the language.
    `aria` gives a fuller spoken name ("Call Roy") for short visible labels ("Call")."""
    attrs = {"href": href if isinstance(href, dict) else {"en": href, "he": href}}
    if aria:
        attrs["aria_label"] = pg.u(aria, to=c["short"])
    tab = ' target="_blank" rel="noopener"' if new_tab else ""
    return f'<a class="{cls}"{pg.at(**attrs)}{tab}>{icon(icon_name)}{pg.tx(pg.u(label, to=c["short"]))}</a>'


def call_button(pg, c, label="call", cls="btn btn-call", aria=None):
    if not c or not c["tel"]:
        return f'<span class="btn is-disabled" aria-disabled="true">{pg.tx(pg.u("missing_phone"))}</span>'
    return link_button(pg, c, href=tel_url(c["tel"]), icon_name="phone", label=label, cls=cls, aria=aria)


def wa_button(pg, c, names, label="whatsapp", cls="btn btn-wa", aria=None):
    if not c or not c["wa"]:
        return ""
    msg = message(pg, c, names)
    href = {lang: wa_url(c["wa"], msg[lang]) for lang in LANGS}
    return link_button(pg, c, href=href, icon_name="whatsapp", label=label, cls=cls, aria=aria, new_tab=True)


def sms_button(pg, c, names, label="sms", cls="btn btn-soft", aria=None):
    if not c or not c["tel"]:
        return ""
    msg = message(pg, c, names)
    href = {lang: sms_url(c["tel"], msg[lang]) for lang in LANGS}
    return link_button(pg, c, href=href, icon_name="sms", label=label, cls=cls, aria=aria)


def email_button(pg, c, names, cls="btn btn-soft"):
    if not c or not c["email"]:
        return ""
    subj = pg.u("email_subject", name=names)
    body = message(pg, c, names)
    href = {lang: mail_url(c["email"], subj[lang], body[lang]) for lang in LANGS}
    return link_button(pg, c, href=href, icon_name="mail", label="btn_email", cls=cls, aria="email")


def hero_contact(pg, names):
    """Primary buttons + owner name and number, shared by every page."""
    o = pg.m["owner"]
    num = ""
    if o and o["tel"]:
        num = (f'<span class="num ltr" dir="ltr" id="owner-num">{esc(o["disp"])}</span>'
               f'<button type="button" class="copy-btn" data-copy="{esc(o["intl"])}" data-copy-target="owner-num" hidden>'
               f'{icon("copy")}{pg.tx(pg.u("copy_number"))}</button>')
    return (f'<div class="actions" id="contact-actions">{call_button(pg, o)}{wa_button(pg, o, names)}</div>'
            f'<p class="owner-line"><span>{pg.tx(pg.u("owner_label"))}:</span> <strong>{pg.tx(o["name"]) if o else ""}</strong> {num}</p>')


def more_actions(pg, names):
    o = pg.m["owner"]
    return (f'<div class="more-actions">{sms_button(pg, o, names)}'
            f'<a class="btn btn-soft" href="#contacts">{icon("users")}{pg.tx(pg.u("more_contacts"))}</a></div>')


def contacts_section(pg, names):
    people = []
    for role, c in (("role_owner", pg.m["owner"]), ("role_backup", pg.m["backup"])):
        if not c:
            continue
        rid = "num-" + role
        nums = ""
        if c["tel"]:
            nums = (f'<p class="num-line"><span class="num ltr" dir="ltr" id="{rid}">{esc(c["disp"])}</span>'
                    f'<span class="fine ltr" dir="ltr">{esc(c["intl"])}</span></p>')
        btns = [
            call_button(pg, c, label="btn_call", aria="call") if c["tel"] else "",
            wa_button(pg, c, names, label="btn_whatsapp", aria="whatsapp"),
            sms_button(pg, c, names, label="btn_sms", aria="sms"),
            email_button(pg, c, names),
        ]
        if c["tel"]:
            btns.append(f'<button type="button" class="btn btn-soft" data-copy="{esc(c["intl"])}" data-copy-target="{rid}" hidden>'
                        f'{icon("copy")}{pg.tx(pg.u("copy_number"))}</button>')
        mail = f'<p class="email-line fine"><span class="ltr" dir="ltr">{esc(c["email"])}</span></p>' if c["email"] else ""
        people.append(f'<article class="card person">{pg.tx(pg.u(role), tag="p", cls="role")}{pg.tx(c["name"], tag="h3")}'
                      f'{nums}<div class="contact-grid">{"".join(btns)}</div>{mail}</article>')
    return (f'<section class="section" id="contacts" aria-labelledby="contacts-title">'
            f'<h2 id="contacts-title">{icon("users")}{pg.tx(pg.u("contacts_title"))}</h2>'
            f'<div class="people">{"".join(people)}</div></section>')


def sticky_bar(pg, names):
    o = pg.m["owner"]
    return (f'<div class="sticky-bar" role="region"{pg.at(aria_label=pg.u("quick_contact"))}><div class="sticky-inner">'
            f'{call_button(pg, o)}{wa_button(pg, o, names, label="whatsapp_short")}</div></div>')


def document(pg, *, title, description, body, accent=None, og_image=None, canonical=None, assets):
    P = pg.P
    pg.key(title, "title")
    pg.expose("copied", "copy_failed", "photo_counter")
    style = f' style="--accent:{accent[0]};--accent-soft:{accent[1]}"' if accent else ""
    meta = ""
    if canonical:
        meta += f'<link rel="canonical" href="{esc(canonical)}">\n<meta property="og:url" content="{esc(canonical)}">\n'
    meta += (f'<meta property="og:type" content="website">\n<meta property="og:title" content="{esc(title["en"])} · {esc(title["he"])}">\n'
             f'<meta property="og:description" content="{esc(description)}">\n')
    if og_image:
        meta += f'<meta property="og:image" content="{esc(og_image)}">\n'
    banner = ""
    if pg.m["_missing"]:
        items = ", ".join(pg.m["_missing"])
        banner = f'<div class="preview-banner" role="alert">{pg.tx(pg.u("preview_banner", items=items))}</div>'
    i18n = json.dumps(pg.d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'''<!doctype html>
<html lang="en" dir="ltr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title["en"])}</title>
<meta name="description" content="{esc(description)}">
<meta name="robots" content="noindex, nofollow, noarchive, noimageindex">
<meta name="format-detection" content="telephone=no, date=no, email=no, address=no">
<meta name="theme-color" content="#faf7f2">
<meta name="referrer" content="strict-origin-when-cross-origin">
{meta}<link rel="icon" href="{P}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{P}assets/styles.css?v={assets["css"]}">
<script>{HEAD_JS}</script>
</head>
<body{style}>
{sprite()}
{banner}{body}
<div id="bb-toast" class="toast" role="status" aria-live="polite"></div>
<script type="application/json" id="bb-i18n">{i18n}</script>
<script>{APPLY_JS}</script>
<script src="{P}assets/app.js?v={assets["js"]}" defer></script>
</body>
</html>
'''


# ═══════════════════════════════════════════════════════════ pages
def age_parts(pg, dog, today):
    """Age row: '4 years old (born 22 Mar 2022)' — kept current by the inline script."""
    b = dog["born"]
    years = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
    date = {"en": f"{b.day} {MONTHS[b.month - 1]} {b.year}", "he": f"{b.day:02d}.{b.month:02d}.{b.year}"}
    for k in ("age_1", "age_2", "age_n"):
        pg.key(pg.u(k, fem=dog["fem"]), k)
    born = pg.key(pg.u("born_on", fem=dog["fem"], date=date), "born_on")
    if years < 1:
        return None
    k = "age_1" if years == 1 else "age_2" if years == 2 else "age_n"
    txt = {lang: pg.d[k][lang].replace("{n}", str(years)) + f" ({pg.d[born][lang]})" for lang in LANGS}
    return f'<span id="bb-age" data-born="{b.isoformat()}">{esc(txt["en"])}</span>', txt


def dog_page(model, dog, assets):
    pg = Page(model, "../")
    P, u, o = pg.P, pg.u, model["owner"]
    name, fem = dog["name"], dog["fem"]
    main_photo = dog["photos"][0] if dog["photos"] else None

    # --- hero
    if main_photo:
        photo = (f'<div class="hero-photo ph">{picture(pg, main_photo, "(min-width: 820px) 460px, 92vw", eager=True)}'
                 f'{fallback_span(pg)}')
    else:
        # Development placeholder: clearly labelled, never a stand-in dog photo.
        label = fill(PLACEHOLDER_PHOTO, n=name)
        photo = f'<div class="hero-photo ph ph-placeholder">{fallback_span(pg, label)}'
    photo += f'<p class="hero-badge">{icon("paw")}{pg.tx(u("eyebrow"))}</p></div>'
    before, nm, after = split_on(u("greeting"), "name", name)
    meta_bits = [p for p in (dog["breed"], u("male") if dog["sex"] == "male" else u("female") if dog["sex"] == "female" else None) if p]
    meta = pg.tx(join(*meta_bits, sep=" · "), tag="p", cls="meta") if meta_bits else ""
    hero = f'''<section class="hero" aria-labelledby="dog-title">{photo}
<div class="hero-body">
<h1 id="dog-title">{pg.tx(before)}<span class="dog-name">{pg.tx(nm)}</span>{pg.tx(after)}</h1>
{meta}
<p class="found"><strong>{pg.tx(u("found_q"))}</strong> {pg.tx(u("found_a"))}</p>
{hero_contact(pg, name)}
<p class="thanks">{icon("heart")}{pg.tx(u("thanks"))}</p>
{more_actions(pg, name)}
</div></section>'''

    # --- urgent notes, right below the contact area
    notes = list(dog["alerts"]) + ([dog["medical"]] if dog["medical"] else [])
    alerts = ""
    if notes:
        alerts = (f'<section class="section note" aria-labelledby="alerts-title"><h2 id="alerts-title">{icon("info")}'
                  f'{pg.tx(u("alerts_title"))}</h2><ul>{"".join(pg.tx(a, tag="li") for a in notes)}</ul></section>')

    # --- what to do
    steps = [u("step_contact" if o and o["wa"] else "step_call_only", owner=o["short"]), u("step_where", owner=o["short"]), u("step_calm")]
    if model["backup"]:
        steps.append(u("step_backup", owner=o["short"], backup=model["backup"]["short"]))
    steps_html = (f'<section class="section card" aria-labelledby="steps-title"><h2 id="steps-title">{icon("paw")}'
                  f'{pg.tx(u("steps_title"))}</h2><ol class="steps">{"".join(pg.tx(s, tag="li") for s in steps)}</ol></section>')

    # --- gallery
    gallery = ""
    if dog["photos"]:
        n = len(dog["photos"])
        items = []
        for i, ph in enumerate(dog["photos"], 1):
            vs = ph["variants"]
            jpg_set = ", ".join(f"{P}{v['jpg']} {v['w']}w" for v in vs)
            webp_set = ", ".join(f"{P}{v['webp']} {v['w']}w" for v in vs)
            # A plain link to the full photo: works even if JavaScript doesn't.
            items.append(
                f'<li><a class="thumb ph" href="{P}{vs[-1]["jpg"]}" data-srcset="{jpg_set}" data-srcset-webp="{webp_set}">'
                f'{picture(pg, ph, "(min-width: 640px) 240px, 46vw")}{fallback_span(pg)}'
                f'{pg.tx(u("photo_open", i=i, total=n), cls="visually-hidden")}</a></li>')
        gallery = (f'<section class="section" aria-labelledby="gallery-title"><h2 id="gallery-title">{icon("paw")}'
                   f'{pg.tx(u("gallery_title", name=name))}</h2>'
                   f'<ul class="gallery{" is-odd" if n % 2 else ""}" style="--cols:{min(n, 5)}">{"".join(items)}</ul>'
                   f'{pg.tx(u("gallery_hint"), tag="p", cls="fine gallery-hint")}</section>')

    # --- facts (only fields that are filled in)
    today = dt.date.today()
    rows = []

    def row(label, value_html):
        rows.append(f'<div><dt>{pg.tx(u(label))}</dt><dd>{value_html}</dd></div>')

    if dog["breed"]:
        row("f_breed", pg.tx(dog["breed"]))
    if dog["sex"] in ("male", "female"):
        row("f_sex", pg.tx(u(dog["sex"])))
    if dog["born"]:
        ap = age_parts(pg, dog, today)
        if ap:
            row("f_age", ap[0])
    if dog["size"]:
        row("f_size", pg.tx(dog["size"]))
    if dog["weight"]:
        row("f_weight", pg.tx(u("weight_value", n=f'{dog["weight"]:g}')))
    for label, key in (("f_coat", "coat"), ("f_markings", "markings"), ("f_temperament", "temperament"),
                       ("f_dogs", "with_dogs"), ("f_animals", "with_animals"), ("f_medical", "medical")):
        if dog[key]:
            row(label, pg.tx(dog[key]))
    if o and o["area"]:
        row("f_home", pg.tx(o["area"]))
    about = (f'<section class="section card" aria-labelledby="about-title"><h2 id="about-title">{icon("paw")}'
             f'{pg.tx(u("about_title", name=name))}</h2><dl class="facts">{"".join(rows)}</dl></section>') if rows else ""

    # --- footer with a discreet link to the other dog(s)
    links = []
    for other in model["dogs"]:
        if other is dog:
            continue
        img = ""
        if other["photos"]:
            ph = other["photos"][0]
            img = (f'<img src="{P}{ph["variants"][0]["jpg"]}" alt="" width="40" height="40" loading="lazy" '
                   f'style="object-position:{esc(ph["focus"])}">')
        links.append(f'<a href="{P}{other["slug"]}/">{img}{pg.tx(u("other_dog", name=other["name"]))}</a>')
    links.append(f'<a href="{P}">{icon("home")}{pg.tx(u("home_link"))}</a>')
    footer = (f'<footer class="site-footer wrap"><div class="paws" aria-hidden="true"></div>'
              f'<nav class="footer-nav"{pg.at(aria_label=u("more_pages"))}>{"".join(links)}</nav>'
              f'{pg.tx(u("privacy_note"), tag="p", cls="fine")}</footer>')

    body = (f'{topbar(pg, P)}\n<main id="main" class="wrap">\n{hero}\n{alerts}\n'
            f'<div class="two-col-wrap two-col">{steps_html}{about}</div>\n{gallery}\n{contacts_section(pg, name)}\n</main>\n'
            f'{footer}\n{sticky_bar(pg, name)}\n{lightbox(pg, name)}')
    base = model["base_url"]
    og = f'{base}/{main_photo["variants"][min(1, len(main_photo["variants"]) - 1)]["jpg"]}' if base and main_photo else None
    return document(pg, title=u("page_title", name=name),
                    description=f'{u("found_q")["en"]} {u("found_a")["en"]} · {u("found_q")["he"]} {u("found_a")["he"]}',
                    body=body, accent=(dog["accent"], dog["accent_soft"]), og_image=og,
                    canonical=f"{base}/{dog['slug']}/" if base else None, assets=assets)


def lightbox(pg, name):
    return f'''<dialog id="bb-lightbox" class="lightbox"{pg.at(aria_label=pg.u("gallery_title", name=name))}>
<div class="lb-top">{pg.tx(pg.u("gallery_title", name=name), tag="p", cls="lb-title")}
<button type="button" class="lb-btn lb-close">{icon("x")}{pg.tx(pg.u("close"))}</button></div>
<div class="lb-stage"><picture><source type="image/webp" sizes="100vw"><img alt="" sizes="100vw" decoding="async"></picture>{fallback_span(pg)}</div>
<p class="lb-caption"></p>
<div class="lb-nav"><button type="button" class="lb-btn lb-prev"{pg.at(aria_label=pg.u("photo_prev_long"))}>{icon("left", "flip")}{pg.tx(pg.u("photo_prev"))}</button>
<p class="lb-count" aria-live="polite"></p>
<button type="button" class="lb-btn lb-next"{pg.at(aria_label=pg.u("photo_next_long"))}>{pg.tx(pg.u("photo_next"))}{icon("right", "flip")}</button></div>
</dialog>'''


def dog_cards(pg):
    cards = []
    for dog in pg.m["dogs"]:
        bits = [p for p in (dog["breed"], pg.u(dog["sex"]) if dog["sex"] in ("male", "female") else None) if p]
        ph = (f'<span class="ph">{picture(pg, dog["photos"][0], "(min-width: 820px) 360px, 46vw")}{fallback_span(pg)}</span>'
              if dog["photos"] else f'<span class="ph ph-placeholder">{fallback_span(pg)}</span>')
        cards.append(
            f'<li><a class="dog-card" href="{pg.P}{dog["slug"]}/" style="--accent:{dog["accent"]}">{ph}'
            f'<span class="dog-card-body">{pg.tx(dog["name"], cls="dog-card-name")}'
            f'{pg.tx(join(*bits, sep=" · "), cls="dog-card-meta") if bits else ""}'
            f'<span class="dog-card-link">{pg.tx(pg.u("home_card_link", name=dog["name"]))}{icon("right", "flip")}</span>'
            f'</span></a></li>')
    return f'<ul class="dog-cards">{"".join(cards)}</ul>'


def all_names(pg):
    names = [d["name"] for d in pg.m["dogs"]]
    j = pg.u("and_joiner")
    return {lang: f" {j[lang]} ".join(n[lang] for n in names) for lang in LANGS}


def home_page(model, assets, not_found=False):
    prefix = model["base_path"] if not_found else ""
    pg = Page(model, prefix)
    u, o = pg.u, model["owner"]
    names = all_names(pg)
    if not_found:
        intro = (f'{pg.tx(u("home_eyebrow"), tag="p", cls="eyebrow")}<h1 id="home-title">{pg.tx(u("nf_title"))}</h1>'
                 f'{pg.tx(u("nf_text", owner=o["short"]), tag="p", cls="found")}')
        title = u("nf_title")
    else:
        # small round portraits beside the title, so both dogs are recognisable at a glance
        avatars = "".join(
            f'<img src="{d["photos"][0]["variants"][0]["jpg"]}" alt="" width="64" height="64" '
            f'style="object-position:{esc(d["photos"][0]["focus"])};--accent:{d["accent"]}">'
            for d in model["dogs"] if d["photos"])
        intro = (f'<div class="home-title-row"><div>{pg.tx(u("home_eyebrow"), tag="p", cls="eyebrow")}'
                 f'<h1 id="home-title">{pg.tx(model["name"])}</h1></div>'
                 f'<div class="avatars" aria-hidden="true">{avatars}</div></div>'
                 f'<p class="found"><strong>{pg.tx(u("home_found_q"))}</strong> {pg.tx(u("home_found_a", owner=o["short"]))}</p>')
        title = model["name"]
    hero = (f'<section class="home-hero" aria-labelledby="home-title">{intro}{hero_contact(pg, names)}'
            f'<p class="thanks">{icon("heart")}{pg.tx(u("home_thanks"))}</p>{more_actions(pg, names)}</section>')
    who = (f'<section class="section" aria-labelledby="who-title"><h2 id="who-title">{icon("paw")}{pg.tx(u("home_who"))}</h2>'
           f'{dog_cards(pg)}</section>')
    footer = (f'<footer class="site-footer wrap"><div class="paws" aria-hidden="true"></div>'
              f'{pg.tx(u("privacy_note"), tag="p", cls="fine")}</footer>')
    body = (f'{topbar(pg, prefix or "./")}\n<main id="main" class="wrap">\n{hero}\n{who}\n{contacts_section(pg, names)}\n</main>\n'
            f'{footer}\n{sticky_bar(pg, names)}')
    base = model["base_url"]
    og = None
    if base and model["dogs"] and model["dogs"][0]["photos"]:
        og = f'{base}/{model["dogs"][0]["photos"][0]["variants"][1 if len(model["dogs"][0]["photos"][0]["variants"]) > 1 else 0]["jpg"]}'
    return document(pg, title=title,
                    description=f'{u("home_found_q")["en"]} · {u("home_found_q")["he"]}',
                    body=body, og_image=og, canonical=(f"{base}/" if base and not not_found else None),
                    assets=assets)


# ═══════════════════════════════════════════════════════════ collar kit
def check_base_url(base, rep):
    if not base:
        rep.warnings.append("[site] base_url is empty → nfc-kit/ (collar URLs + QR codes) not generated yet. "
                            "Publish first, then set base_url and rebuild.")
        return False
    p = urlparse(base)
    if p.scheme != "https" or not p.netloc:
        rep.warnings.append(f"[site] base_url '{base}' must start with https:// — nfc-kit/ not generated")
        return False
    if any(h in p.netloc.lower() for h in PLACEHOLDER_HOSTS):
        rep.warnings.append(f"[site] base_url '{base}' looks like a placeholder or temporary preview — nfc-kit/ not generated")
        return False
    return True


def build_kit(model, rep):
    base = model["base_url"]
    if KIT.exists():
        shutil.rmtree(KIT)
    KIT.mkdir()
    o = model["owner"]
    entries = [(model["name"]["en"] + " (homepage)", base + "/", None)] + \
              [(d["name"]["en"], f"{base}/{d['slug']}/", d) for d in model["dogs"]]
    cards = []
    for label, url, dog in entries:
        slug = dog["slug"] if dog else "home"
        svg = qr_svg(url, title=f"QR code for {url}")
        (KIT / f"{slug}-qr.svg").write_text(svg, encoding="utf-8")
        photo = ""
        if dog and dog["photos"]:
            photo = f'<img src="../public/{dog["photos"][0]["variants"][0]["jpg"]}" alt="" style="object-position:{esc(dog["photos"][0]["focus"])}">'
        cards.append(f'''<section class="kit-card">
<header>{photo}<div><h2>{esc(label)}</h2><p class="url">{esc(url)}</p></div></header>
<div class="print-label">
  <div class="qr">{svg}</div>
  <p><strong>{esc(dog["name"]["en"] + " · " + dog["name"]["he"]) if dog else esc(model["name"]["en"])}</strong><br>
  Scan me · סרקו אותי<br><span dir="ltr">{esc(o["disp"])}</span></p>
</div>
<p class="file">QR file: <code>nfc-kit/{slug}-qr.svg</code></p>
</section>''')
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>Collar kit — {esc(model["name"]["en"])}</title>
<style>
body{{font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;margin:0;padding:24px;background:#faf7f2;color:#1d2321}}
main{{max-width:880px;margin:0 auto}} h1{{margin:0 0 4px}} .lead{{color:#4b5451;margin:0 0 20px}}
.kit-card{{background:#fff;border-radius:18px;padding:20px;margin:0 0 18px;box-shadow:0 6px 20px rgba(0,0,0,.07);break-inside:avoid}}
.kit-card header{{display:flex;gap:14px;align-items:center}} .kit-card img{{width:64px;height:64px;border-radius:50%;object-fit:cover}}
.kit-card h2{{margin:0;font-size:1.3rem}} .url{{font:700 1.15rem/1.3 ui-monospace,Consolas,monospace;margin:4px 0 0;word-break:break-all;user-select:all}}
.print-label{{display:inline-flex;gap:14px;align-items:center;border:1.5px dashed #bbb;border-radius:12px;padding:12px 16px;margin-top:14px}}
.qr svg{{width:30mm;height:30mm;display:block}} .file{{color:#4b5451;font-size:.9rem;margin:10px 0 0}}
ol li{{margin:6px 0}} .box{{background:#fff;border-radius:18px;padding:20px;margin-top:24px}}
@media print{{body{{background:#fff;padding:0}} .box,.lead{{display:none}} .kit-card{{box-shadow:none;border:1px solid #ddd}}}}
</style></head><body><main>
<h1>Collar kit</h1>
<p class="lead">Built from base_url <strong>{esc(base)}</strong>. Write each URL to its tag exactly as shown; the QR codes are an optional printed backup.</p>
{"".join(cards)}
<section class="box"><h2>Before trusting the collars</h2><ol>
<li>Open each URL above on your phone (mobile data, not Wi-Fi) and check it shows the right dog.</li>
<li>Write the URL to the NFC tag (e.g. the free “NFC Tools” app → Write → Add a record → URL).</li>
<li>Scan each tag with an iPhone <em>and</em> an Android phone. Tap Call and WhatsApp on both — check the number and that the message names the right dog.</li>
<li>Scan each printed QR code with a phone camera.</li>
<li>Only then consider locking the tag (optional and permanent — a locked tag can never be rewritten).</li>
<li>Keep the phone number engraved on the physical tag too: NFC only stores this link, it is not a GPS tracker, and a finder needs internet to open the page.</li>
</ol></section>
</main></body></html>'''
    (KIT / "index.html").write_text(page, encoding="utf-8")
    rep.done.append("nfc-kit/ written: " + ", ".join(url for _, url, _ in entries))


# ═══════════════════════════════════════════════════════════ main
HEADERS = """# Response headers for Cloudflare Pages / Netlify (ignored by GitHub Pages).
/*
  X-Robots-Tag: noindex, nofollow, noarchive
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=()

/assets/*
  Cache-Control: public, max-age=31536000, immutable

/photos/*
  Cache-Control: public, max-age=31536000, immutable
"""


def print_report(rep):
    print("\nBob & Berry build")
    for d in rep.done:
        print("  ✓", d)
    for w in rep.warnings:
        print("  !", w)
    if rep.missing:
        print("\n  ✗ NOT READY FOR COLLAR USE — essential information missing:")
        for m in rep.missing:
            print("     -", m)
        print("    (every page shows a red preview banner until this is fixed)")
    else:
        print("  ✓ all essential information present")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    rep = Report()
    model = load_config(rep)
    model["_missing"] = rep.missing
    if "--check" in sys.argv:
        check_base_url(model["base_url"], rep)
        print_report(rep)
        return 1 if rep.missing else 0

    # fresh output, but keep already-resized photos
    OUT.mkdir(exist_ok=True)
    for p in OUT.iterdir():
        if p.name == "photos":
            continue
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    (OUT / "assets").mkdir()
    for f in ("styles.css", "app.js"):
        shutil.copyfile(SRC / f, OUT / "assets" / f)
    assets = {"css": file_hash(SRC / "styles.css"), "js": file_hash(SRC / "app.js")}
    (OUT / "favicon.svg").write_text(FAVICON, encoding="utf-8")
    (OUT / "_headers").write_text(HEADERS, encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    process_photos(model, rep)

    (OUT / "index.html").write_text(home_page(model, assets), encoding="utf-8")
    (OUT / "404.html").write_text(home_page(model, assets, not_found=True), encoding="utf-8")
    for dog in model["dogs"]:
        (OUT / dog["slug"]).mkdir(exist_ok=True)
        (OUT / dog["slug"] / "index.html").write_text(dog_page(model, dog, assets), encoding="utf-8")
    rep.done.append("public/ written: / " + " ".join(f"/{d['slug']}/" for d in model["dogs"]) + " + 404")

    if check_base_url(model["base_url"], rep) and not rep.missing:
        build_kit(model, rep)
    elif KIT.exists():
        shutil.rmtree(KIT)
    print_report(rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
