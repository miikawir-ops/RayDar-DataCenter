"""Finnish/English parity for the business-models explainer (ledger R104).

For every page in business-models/ that has an English version under the same
file name in business-models/en/, and for the two glossary data files, compare
the pages block by block: the same dates, the same numbers (amounts,
percentages, years, ranges) and the same company and place names. A block is a
non-inline element with text, matched across the two pages by its place in the
page (the English pages keep the Finnish markup); alt, aria-label, title and the
description and og tags count as blocks of their own. Any mismatch fails,
unless an entry in tools/lang_parity_allow.json names it with a reason.

How the sides are made comparable:
  - dates first, as canonical tokens: 1.7.2026 / 1 July 2026, 9/2026 /
    syyskuu(ssa) 2026 / September 2026;
  - then numbers: Finnish 1,5 and 10 500 become 1.5 and 10500, English 10,500
    becomes 10500; each block's numbers are compared as a multiset;
  - names: a capitalised word that doesn't start the block or a sentence, in
    either language, must appear on the other side too (anywhere there,
    sentence starts included). Finnish inflects names
    (Helsingin, Microsoftin), so two words match when they share a prefix of
    at least max(min(4, shorter), shorter - 3) letters (Owl / Owlilta); translated place names (Suomi /
    Finland) are listed in EXONYMS. All-caps labels are left to the numbers.

    python tools/check_lang_parity.py                  # the repo's pages
    python tools/check_lang_parity.py --root <copy>    # a copy (e.g. the failure proof)

Exit code 0 when every pair matches, 1 otherwise. tools/check_port_text.py stays
the Finnish pages' check against the design source; this one checks the English
pages against the Finnish ones.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from html.parser import HTMLParser

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW_FILE = os.path.join(REPO, "tools", "lang_parity_allow.json")

INLINE = {"a", "abbr", "b", "br", "code", "em", "i", "small", "span", "strong", "sub", "sup", "wbr", "s", "u", "time"}
SKIP = {"script", "style"}
TEXT_ATTRS = ("alt", "aria-label", "title")
META = {"description", "og:title", "og:description", "og:image:alt"}
# Place names written differently in the two languages (Finnish base form -> English).
# A Finnish word can stand for several English ones (Yhdysvallat / United States).
EXONYMS = {"Suomi": ["Finland"], "Saksa": ["Germany"], "Ruotsi": ["Sweden"], "Norja": ["Norway"], "Tanska": ["Denmark"],
           "Tukholma": ["Stockholm"], "Kööpenhamina": ["Copenhagen"], "Teksas": ["Texas"],
           "Yhdysvallat": ["United", "States"], "Pohjois": ["North"], "Amerikka": ["America"],
           "Keski": ["Central"], "Pohjoismaat": ["Nordic"],
           "Eurooppa": ["Europe"], "Kanada": ["Canada"], "Israel": ["Israeli"]}
FI_MONTHS = ["tammi", "helmi", "maalis", "huhti", "touko", "kesä", "heinä", "elo", "syys", "loka", "marras", "joulu"]
EN_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
             "november", "december"]


class Blocks(HTMLParser):
    """Text per block, keyed by the block's path of (tag, sibling index)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.counts, self.blocks, self.labels, self.skip = [], [{}], {}, {}, 0

    def _key(self):
        return tuple((t, i) for t, i, _, blk in self.stack if blk)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in SKIP:
            self.skip += 1
        if tag == "br" and self.stack:
            # A line break starts a new line of text: the word after it is a start, like after a full stop.
            blk = [st for st in self.stack if st[3]]
            self._add(self._key(), "|", blk[-1][2] if blk else "?", append=True)
        if tag in ("br", "wbr", "meta", "link", "img", "input", "col", "source"):
            if tag == "meta" and (a.get("name") or a.get("property")) in META:
                self._add(("head", a.get("name") or a.get("property")), a.get("content") or "", "meta " + (a.get("name") or a.get("property")))
            if tag == "img":
                self._attrs(tag, a)
            return
        i = self.counts[-1].get(tag, 0)
        self.counts[-1][tag] = i + 1
        label = tag + ("#" + a["id"] if a.get("id") else "") + ("." + a["class"].split()[0] if a.get("class") else "")
        # A span with data-key is one of a script's separate strings: a block of its own.
        self.stack.append((tag, i, label, tag not in INLINE or "data-key" in a))
        self.counts.append({})
        self._attrs(tag, a)

    def _attrs(self, tag, a):
        for at in TEXT_ATTRS:
            if a.get(at):
                key = self._key() + ((tag, "@" + at),)
                self._add(key, a[at], (self.stack[-1][2] if self.stack else tag) + "@" + at)

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip -= 1
        for j in range(len(self.stack) - 1, -1, -1):
            if self.stack[j][0] == tag:
                del self.stack[j:]
                del self.counts[j + 1:]
                break

    def handle_data(self, data):
        if self.skip or not data.strip():
            return
        blk = [s for s in self.stack if s[3]]
        self._add(self._key(), data, blk[-1][2] if blk else "?", append=True)

    def _add(self, key, text, label, append=False):
        # Pieces of one block (text around inline elements) are joined with a space,
        # so two separate labels never run into one word.
        self.blocks[key] = (self.blocks[key] + " " + text) if key in self.blocks else text
        self.labels.setdefault(key, label)


def parse(path):
    p = Blocks()
    p.feed(open(path, encoding="utf-8").read())
    return {k: re.sub(r"\s+", " ", v.replace("­", "")).strip() for k, v in p.blocks.items()}, p.labels


def dates(text, lang):
    """(canonical date tokens, the text with them removed)."""
    found = []

    def take(tok):
        found.append(tok)
        return " "
    t = re.sub(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", lambda m: take(f"{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}"), text)
    t = re.sub(r"\b(\d{1,2})\.(\d{1,2})\.(?=[–-]\d{1,2}\.\d{1,2}\.\d{4})", lambda m: take(f"--{int(m[2]):02d}-{int(m[1]):02d}"), t)
    t = re.sub(r"\b(\d{1,2})/(\d{4})\b", lambda m: take(f"{m[2]}-{int(m[1]):02d}"), t)
    if lang == "fi":
        t = re.sub(r"\b(" + "|".join(FI_MONTHS) + r")(?:kuu|kuussa|kuun|kuuta|kuusta|kuuhun)\s+(\d{4})\b",
                   lambda m: take(f"{m[2]}-{FI_MONTHS.index(m[1].lower()) + 1:02d}"), t, flags=re.I)
    else:
        mon = "|".join(EN_MONTHS)
        t = re.sub(r"\b(\d{1,2})\s+(" + mon + r")\s+(\d{4})\b",
                   lambda m: take(f"{m[3]}-{EN_MONTHS.index(m[2].lower()) + 1:02d}-{int(m[1]):02d}"), t, flags=re.I)
        t = re.sub(r"\b(" + mon + r")\s+(\d{1,2}),\s+(\d{4})\b",
                   lambda m: take(f"{m[3]}-{EN_MONTHS.index(m[1].lower()) + 1:02d}-{int(m[2]):02d}"), t, flags=re.I)
        t = re.sub(r"\b(\d{1,2})\s+(" + mon + r")(?=\s*[–-]\s*\d{1,2}\s+(?:" + mon + r")\s+\d{4})",
                   lambda m: take(f"--{EN_MONTHS.index(m[2].lower()) + 1:02d}-{int(m[1]):02d}"), t, flags=re.I)
        t = re.sub(r"\b(" + mon + r")\s+(\d{4})\b",
                   lambda m: take(f"{m[2]}-{EN_MONTHS.index(m[1].lower()) + 1:02d}"), t, flags=re.I)
    return found, t


def numbers(text, lang):
    t = text
    if lang == "fi":
        t = re.sub(r"(?<=\d)[   ](?=\d{3}\b)", "", t)
        t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    else:
        t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)
    return [n.rstrip(".") for n in re.findall(r"\d+(?:\.\d+)?", t)]


def names(text):
    """Capitalised words that don't start the block or a sentence."""
    out = []
    if text == text.upper():
        return out            # an all-caps label (a kicker): its words aren't names
    for m in re.finditer(r"[A-ZÅÄÖ][\wÅÄÖåäö&]*(?:-[\wÅÄÖåäö]+)*", text):
        before = text[:m.start()].rstrip()
        if not before or before[-1] in ".!?:·•–—(\"“'‘|←→*▼▲" or before.endswith("<br>"):
            continue
        w = m.group(0).split("-")[0].split(":")[0]
        if (w.isupper() and len(w) > 1) or (w.endswith("s") and w[:-1].isupper() and len(w) > 2):
            continue          # acronyms (GPU, GPUs) and all-caps labels: the numbers cover them
        if len(w) == 1:
            continue          # a single letter: a unit (30 M€) or a list mark, not a name
        if w.lower() in EN_MONTHS:
            continue          # a month in a date, not a name (the dates are compared above)
        out.append(w)
    return out


def capitalised(text):
    """Every capitalised word, wherever it stands: what a name is looked for in. Each capitalised
    part of a hyphenated word counts (Pohjois-Amerikassa gives Pohjois and Amerikassa)."""
    out = []
    for m in re.finditer(r"[A-ZÅÄÖ][\wÅÄÖåäö&]*(?:[-:][\wÅÄÖåäö]+)*", text):
        out += [part for part in re.split(r"[-:]", m.group(0)) if part[:1].isupper()]
    return out


def same_name(a, b):
    k = 0
    while k < min(len(a), len(b)) and a[k].lower() == b[k].lower():
        k += 1
    short = min(len(a), len(b))
    return k >= max(min(4, short), short - 3)


def base_exonym(word):
    """The EXONYMS entries (their Finnish keys) a word belongs to, in either language."""
    return {fi for fi, ens in EXONYMS.items() if same_name(word, fi) or any(same_name(word, en) for en in ens)}


def name_missing(word, other_words):
    ex = base_exonym(word)
    if ex:
        return not any(base_exonym(o) & ex for o in other_words)
    return not any(same_name(word, o) for o in other_words)


def glossary(path):
    src = open(path, encoding="utf-8").read()
    out = {}
    for m in re.finditer(r'^\s*([a-z_]+): \{(.*)\},?\s*$', src, re.M):
        vals = re.findall(r'(term|alt|definition): "((?:[^"\\]|\\.)*)"', m[2])
        out[m[1]] = " · ".join(v for _, v in vals)
    return out


def allowed(allow, page, label, kind, value):
    for a in allow:
        if a["page"] in (page, "*") and a["kind"] == kind and a["value"] in (value, "*") and a.get("block", "*") in ("*", label):
            a["used"] = True
            return True
    return False


def compare(page, fi, en, fi_labels, allow, problems):
    for key in sorted(set(fi) | set(en), key=str):
        label = (fi_labels.get(key) if key in fi_labels else None) or "?"
        if key not in en or key not in fi:
            side = "Finnish" if key in fi else "English"
            text = (fi.get(key) or en.get(key))[:60]
            if not allowed(allow, page, label, "block", label):
                problems.append(f"{page}: block {label} only on the {side} page: \"{text}\"")
            continue
        a, b = fi[key], en[key]
        da, ra = dates(a, "fi")
        db, rb = dates(b, "en")
        for tok in (Counter(da) - Counter(db)) + (Counter(db) - Counter(da)):
            if not allowed(allow, page, label, "date", tok):
                problems.append(f"{page}: {label}: date {tok} differs\n    fi: {a[:140]}\n    en: {b[:140]}")
        na, nb = Counter(numbers(ra, "fi")), Counter(numbers(rb, "en"))
        for n in sorted(set((na - nb) | (nb - na))):
            if not allowed(allow, page, label, "number", n):
                problems.append(f"{page}: {label}: number {n} fi x{na[n]}, en x{nb[n]}\n    fi: {a[:140]}\n    en: {b[:140]}")
        wa, wb = capitalised(a), capitalised(b)
        for w, other, side in [(w, wb, "Finnish") for w in names(a)] + [(w, wa, "English") for w in names(b)]:
            if name_missing(w, other) and not allowed(allow, page, label, "name", w):
                problems.append(f"{page}: {label}: name \"{w}\" only on the {side} side\n    fi: {a[:140]}\n    en: {b[:140]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=os.path.join(REPO, "business-models"), help="the Finnish pages' folder (en/ inside it)")
    args = ap.parse_args()
    allow = json.load(open(ALLOW_FILE, encoding="utf-8"))["allow"]
    root, problems, pairs = args.root, [], 0
    for name in sorted(os.listdir(os.path.join(root, "en"))):
        if not name.endswith(".html"):
            continue
        fi_path, en_path = os.path.join(root, name), os.path.join(root, "en", name)
        if not os.path.exists(fi_path):
            problems.append(f"en/{name}: no Finnish page {name}")
            continue
        fi, fi_labels = parse(fi_path)
        en, _ = parse(en_path)
        compare(name, fi, en, fi_labels, allow, problems)
        pairs += 1
    gfi, gen = (os.path.join(root, "assets", f) for f in ("glossary-fi.js", "glossary-en.js"))
    if os.path.exists(gen):
        a, b = glossary(gfi), glossary(gen)
        keys = sorted(set(a) | set(b))
        compare("glossary data", {(k,): a[k] for k in keys if k in a}, {(k,): b[k] for k in keys if k in b},
                {(k,): k for k in keys}, allow, problems)
        pairs += 1
    for p in problems:
        print("FAIL " + p)
    stale = [a for a in allow if not a.get("used") and a["page"] != "*"]
    for a in stale:
        print(f"note: allowlist entry not used: {a['page']} {a['kind']} {a['value']} ({a.get('block', '*')})")
    print(f"\n{pairs} page pairs; {len(problems)} mismatches")
    return 1 if problems or not pairs else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
