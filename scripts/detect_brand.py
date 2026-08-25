#!/usr/bin/env python3
"""Read a codebase and work out its brand: colours, fonts, logo, icon set.

Point it at a product repo and it reports the palette, fonts, icon library and
logo files, so a video matches the product without anyone eyedropping a
screenshot. Paste the values into the :root block of deck.html.

    python3 scripts/detect_brand.py ../my-product
    python3 scripts/detect_brand.py ../my-product --css     # ready for deck.html

What it reads, highest confidence first:

  1. design token files      tokens.json, design-tokens.json, theme.json
  2. tailwind config         theme.extend.colors
  3. CSS custom properties   --brand-*, --color-*, --primary
  4. SCSS / Less variables   $primary, @brand
  5. JS/TS theme objects     theme.ts, colors.ts, palette.ts
  6. web manifest            theme_color, background_color
  7. package.json            icon and font libraries in use
  8. asset directories       files with "logo" in the name

Build output is skipped. A dist/ folder is full of vendored CSS from whatever
component libraries the product uses, and those colours are not the brand.
"""
import argparse, json, pathlib, re, sys
from collections import Counter

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "out", ".next", ".nuxt", "vendor",
    "coverage", "__pycache__", ".venv", "venv", "target", ".cache", "public/build",
    "site-packages", ".tox", "bower_components", "tmp", ".turbo",
}
HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
# CSS generic families and keywords are not brand fonts
GENERIC_FONT = re.compile(
    r"^(var\(|inherit|initial|unset|revert|none|sans-serif|serif|monospace|cursive|"
    r"fantasy|system-ui|ui-\w+|-apple-\w+|BlinkMacSystemFont|emoji|math|fangsong)",
    re.I)

# Token names that indicate a deliberate brand decision, best first.
ROLE_HINTS = {
    "accent":  ["brand", "primary", "accent", "action", "cta", "link", "interactive"],
    "bg":      ["background", "bg", "surface-base", "canvas", "page", "backdrop"],
    "surface": ["surface", "card", "panel", "elevated", "muted", "secondary-bg"],
    "ink":     ["foreground", "text", "ink", "on-background", "content"],
    "alert":   ["danger", "error", "destructive", "critical", "alert", "warning"],
}


def norm(h):
    h = h.lstrip("#").lower()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h[:6].upper()


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luma(h):
    r, g, b = rgb(h)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


def sat(h):
    r, g, b = [v / 255 for v in rgb(h)]
    mx, mn = max(r, g, b), min(r, g, b)
    return 0 if mx == 0 else (mx - mn) / mx


def walk(root):
    for p in root.rglob("*"):
        if p.is_file() and not any(part in SKIP_DIRS for part in p.parts):
            yield p


def scan(root):
    """Return {name: (hex, source)} for every named colour token found."""
    named, srcs = {}, Counter()

    def add(name, value, source):
        v = norm(value)
        key = name.strip().lower().lstrip("-$@").strip("'\" ")
        if key and key not in named:
            named[key] = (v, source)
            srcs[source] += 1

    for p in walk(root):
        suf, name = p.suffix.lower(), p.name.lower()
        try:
            if suf in {".css", ".scss", ".sass", ".less", ".styl"}:
                t = p.read_text(errors="ignore")
                for m in re.finditer(r"(--[\w-]+)\s*:\s*(" + HEX.pattern + ")", t):
                    add(m.group(1), m.group(2), "css-var")
                for m in re.finditer(r"([$@][\w-]+)\s*:\s*(" + HEX.pattern + ")", t):
                    add(m.group(1), m.group(2), "preprocessor-var")

            elif name.startswith("tailwind.config"):
                t = p.read_text(errors="ignore")
                for m in re.finditer(r"['\"]?([\w-]+)['\"]?\s*:\s*['\"](" + HEX.pattern + ")['\"]", t):
                    add(m.group(1), m.group(2), "tailwind")

            elif name in {"tokens.json", "design-tokens.json", "theme.json"}:
                def rec(o, path=""):
                    if isinstance(o, dict):
                        for k, v in o.items():
                            rec(v, f"{path}-{k}" if path else k)
                    elif isinstance(o, str) and HEX.fullmatch(o.strip()):
                        add(path, o.strip(), "token-file")
                rec(json.loads(p.read_text(errors="ignore")))

            elif name in {"site.webmanifest", "manifest.json"} and p.stat().st_size < 40_000:
                d = json.loads(p.read_text(errors="ignore"))
                for k in ("theme_color", "background_color"):
                    if isinstance(d.get(k), str) and HEX.fullmatch(d[k].strip()):
                        add(k, d[k].strip(), "manifest")

            elif suf in {".ts", ".tsx", ".js", ".jsx"} and re.search(
                    r"(theme|palette|colou?rs?|tokens)\b", name):
                t = p.read_text(errors="ignore")[:60_000]
                for m in re.finditer(r"['\"]?([\w-]+)['\"]?\s*:\s*['\"](" + HEX.pattern + ")['\"]", t):
                    add(m.group(1), m.group(2), "js-theme")
        except Exception:
            continue
    return named, srcs


def pick(named):
    """Map named tokens onto the deck's roles, best-effort."""
    out, why = {}, {}
    for role, hints in ROLE_HINTS.items():
        best = None
        for hint in hints:                       # earlier hint wins
            for key, (val, src) in named.items():
                if hint in key:
                    # skip obvious state variants
                    if re.search(r"(hover|active|focus|disabled|dark|light|50|100|900)$", key):
                        continue
                    best = (key, val, src)
                    break
            if best:
                break
        if best:
            out[role], why[role] = best[1], f"{best[0]} ({best[2]})"
    return out, why


def infer_missing(out, why, named):
    """Fill gaps from the colour distribution rather than leaving them blank."""
    vals = [v for v, _ in named.values()]
    # keep the most saturated colour aside; validate() may need it as a fallback
    cands = [v for v in vals if sat(v) > 0.35 and 0.25 < luma(v) < 0.95]
    if cands:
        out["_saturated"] = max(cands, key=sat)
    if not vals:
        return
    if "bg" not in out:
        d = min(vals, key=luma)
        out["bg"], why["bg"] = d, "darkest colour found (inferred)"
    if "accent" not in out:
        cand = [v for v in vals if sat(v) > 0.35 and 0.25 < luma(v) < 0.95]
        if cand:
            a = max(cand, key=sat)
            out["accent"], why["accent"] = a, "most saturated colour (inferred)"
    if "ink" not in out:
        out["ink"], why["ink"] = ("#FFFFFF" if luma(out.get("bg", "#000000")) < 0.5
                                  else "#111111"), "contrast with bg (inferred)"


def validate(theme, why):
    """Reject values that are individually plausible but incoherent together.

    Name matching finds tokens, not palettes. A repo can define --surface for a
    light theme and --bg for a dark one, and taking both gives a white card on a
    black slide. Anything rejected here is reported, never silently swapped.
    """
    notes = []
    bg = theme.get("bg")
    if not bg:
        return notes
    dark = luma(bg) < 0.5

    # surface must sit near the background, or cards look like holes
    sf = theme.get("surface")
    if sf and abs(luma(sf) - luma(bg)) > 0.30:
        notes.append(f"surface {sf} rejected: luma {luma(sf):.2f} vs bg {luma(bg):.2f}, "
                     f"not the same theme")
        theme["surface"] = shift(bg, 0.06 if dark else -0.05)
        why["surface"] = "derived from bg (detected value was a different theme)"

    # an accent with no saturation cannot carry emphasis
    ac = theme.get("accent")
    if ac and sat(ac) < 0.25:
        alt = theme.pop("_saturated", None)
        notes.append(f"accent {ac} rejected: saturation {sat(ac):.2f} is too low to "
                     f"read as an accent")
        if alt:
            theme["accent"], why["accent"] = alt, "most saturated colour (name match was grey)"
        else:
            theme.pop("accent", None)
            why.pop("accent", None)

    # text must contrast with the background
    ik = theme.get("ink")
    if ik and abs(luma(ik) - luma(bg)) < 0.4:
        notes.append(f"ink {ik} rejected: too little contrast with bg")
        theme["ink"] = "#FFFFFF" if dark else "#111111"
        why["ink"] = "contrast with bg (detected value failed)"
    return notes


def shift(hexv, amount):
    """Lighten (positive) or darken (negative) a colour, clamped."""
    r, g, b = rgb(hexv)
    f = lambda v: max(0, min(255, int(v + amount * 255)))
    return "#%02X%02X%02X" % (f(r), f(g), f(b))


def assets(root):
    """Logos, fonts and the icon library."""
    logos, fonts, icons = [], set(), set()
    ICON_PKGS = ["lucide", "@heroicons", "react-icons", "feather-icons", "@phosphor",
                 "@tabler/icons", "bootstrap-icons", "@fortawesome", "iconoir", "remixicon"]
    for p in walk(root):
        n = p.name.lower()
        if "logo" in n or n.startswith(("brand.", "wordmark", "icon-")):
            if p.suffix.lower() in {".svg", ".png", ".webp"} and p.stat().st_size < 3_000_000:
                logos.append(p)
        elif n == "package.json":
            try:
                d = json.loads(p.read_text(errors="ignore"))
                deps = {**d.get("dependencies", {}), **d.get("devDependencies", {})}
                for dep in deps:
                    if any(dep.startswith(i) or dep == i for i in ICON_PKGS):
                        icons.add(dep)
                    if dep.startswith("@fontsource"):
                        fonts.add(dep.split("/")[-1].replace("-", " ").title())
            except Exception:
                pass
        elif p.suffix.lower() in {".css", ".scss"}:
            try:
                for m in re.finditer(r"font-family\s*:\s*([^;{}]+)", p.read_text(errors="ignore")):
                    first = m.group(1).split(",")[0].strip().strip("'\"")
                    first = first.replace("!important", "").strip()
                    if first and not GENERIC_FONT.match(first):
                        fonts.add(first)
            except Exception:
                pass
    logos.sort(key=lambda p: (p.suffix.lower() != ".svg", len(p.parts)))
    return logos[:5], sorted(fonts)[:6], sorted(icons)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", help="path to the product codebase")
    ap.add_argument("--json", action="store_true", help="print only the theme JSON")
    ap.add_argument("--css", action="store_true",
                    help="print a :root block to paste into deck.html")
    a = ap.parse_args()

    root = pathlib.Path(a.repo).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"not a directory: {root}")

    named, srcs = scan(root)
    theme, why = pick(named)
    infer_missing(theme, why, named)
    notes = validate(theme, why)
    theme.pop("_saturated", None)
    logos, fonts, icons = assets(root)

    if a.json:
        print(json.dumps({"theme": theme}, indent=2))
        return
    if a.css:
        print(":root{")
        for k, v in theme.items():
            print(f"  --{k}: {v};")
        print("}")
        return

    print(f"scanned {root}")
    if not named:
        print("  no colour tokens found. Is this the right directory, and does it")
        print("  keep colours in CSS variables, a tailwind config or a token file?")
    else:
        print(f"  {len(named)} colour tokens from: " +
              ", ".join(f"{k} x{v}" for k, v in srcs.most_common()))
    print()
    print("  theme")
    for k, v in theme.items():
        print(f"    {k:<8} {v}   <- {why.get(k,'')}")
    if notes:
        print("\n  rejected (kept the deck coherent)")
        for n in notes:
            print(f"    {n}")
    if fonts:
        print(f"\n  fonts     {', '.join(fonts)}")
    if icons:
        print(f"  icons     {', '.join(icons)}")
    if logos:
        print("  logos")
        for l in logos:
            print(f"    {l.relative_to(root)}")

    print("\n  paste into the :root block of deck.html:")
    for k, v in theme.items():
        print(f"    --{k}: {v};")


    print("\n  Detection is a starting point, not an answer. Check the result against")
    print("  the product before sending the deck to anyone.")


if __name__ == "__main__":
    main()
