"""Check that a ported business-models page kept every word of its approved source.

Compares the visible text of a Claude Design export (Output/business-models-source/
*.dc.html) with its port in business-models/, in document order. Formatting,
markup and whitespace are ignored; any added, dropped or changed word is reported.

Known, intentional differences live in tools/port_deviations.json, which is applied
automatically (pass --no-registry to see the raw differences):
  ignore_class    text the port adds on purpose (e.g. matrix row labels repeated in
                  each cell for phones), excluded from the port
  expect_removed  word sequences the port drops on purpose (e.g. the model cards'
                  in-page stepper); each must occur exactly once in the source
  replace         word sequences the port deliberately rewords (e.g. the review-date
                  label); each must occur at least once in the source
  unordered       compare text blocks regardless of order (canvas sources)
  glossary_data   compare the source with the JS data file a page renders from
A deviation whose text no longer appears in the source is an error too, so the
registry can't go stale silently. Anything not in the registry still fails.

Usage:
    python tools/check_port_text.py --all
    python tools/check_port_text.py Output/business-models-source/Main.dc.html business-models/index.html

Exit code 0 when every compared text matches, 1 otherwise.
"""
import argparse
import difflib
import json
import os
import re
import sys
from collections import Counter
from html.parser import HTMLParser

REGISTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "port_deviations.json")
SKIP_TAGS = {"script", "style", "head", "title", "helmet", "noscript"}
INLINE_TAGS = {"a", "abbr", "b", "bdi", "bdo", "cite", "code", "em", "i", "kbd", "mark",
               "q", "s", "small", "span", "strong", "sub", "sup", "u"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
             "param", "source", "track", "wbr"}


class TextExtractor(HTMLParser):
    def __init__(self, ignore_classes):
        super().__init__(convert_charrefs=True)
        self.ignore_classes = set(ignore_classes)
        self.stack = []  # one bool per open element: is it (or an ancestor) skipped?
        self.parts = []

    def _skipped(self):
        return bool(self.stack) and self.stack[-1]

    def handle_starttag(self, tag, attrs):
        classes = set((dict(attrs).get("class") or "").split())
        if tag not in INLINE_TAGS:
            self.parts.append("\n")  # block boundary separates words
        if tag in VOID_TAGS:
            return
        self.stack.append(self._skipped() or tag in SKIP_TAGS or bool(classes & self.ignore_classes))

    def handle_startendtag(self, tag, attrs):
        if tag not in INLINE_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if self.stack:
            self.stack.pop()
        if tag not in INLINE_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skipped():
            self.parts.append(data)

    def words(self):
        return "".join(self.parts).split()

    def blocks(self):
        """Text of each block-level run (box, label, paragraph line), whitespace-normalised."""
        return [" ".join(b.split()) for b in "".join(self.parts).split("\n") if b.strip()]


def parse(path, ignore_classes=()):
    parser = TextExtractor(ignore_classes)
    with open(path, encoding="utf-8") as f:
        parser.feed(f.read())
    return parser


def page_words(path, ignore_classes=()):
    return parse(path, ignore_classes).words()


def glossary_words(data_path):
    """Words of every entry in a glossary-fi.js style file: term, alt, definition, in order."""
    src = open(data_path, encoding="utf-8").read()
    words = []
    for entry in re.finditer(r"^\s+\w+: \{(.*)\},\s*$", src, re.M):
        fields = dict(re.findall(r'(\w+): ("(?:[^"\\]|\\.)*")', entry.group(1)))
        for name in ("term", "alt", "definition"):
            if name in fields:
                words += json.loads(fields[name]).split()
    return words


def apply_seq(words, seq_from, seq_to, exactly_once):
    """Replace every occurrence of word sequence seq_from with seq_to; returns (words, count)."""
    out, i, n = [], 0, 0
    while i < len(words):
        if words[i:i + len(seq_from)] == seq_from:
            out += seq_to
            i += len(seq_from)
            n += 1
        else:
            out.append(words[i])
            i += 1
    if exactly_once and n != 1:
        return words, n
    return out, n


def check(source, port, ignore_class=(), expect_removed=(), replace=(), unordered=False, glossary_data=None):
    """Returns (ok, lines of report)."""
    msgs = []
    if unordered:
        sb, pb = Counter(parse(source).blocks()), Counter(parse(port, ignore_class).blocks())
        for old, new in replace:
            hits = sum(c for b, c in sb.items() if old in b)
            if not hits:
                return False, [f"ERROR: registry replacement not found in source (stale entry?): {old!r}"]
            sb = Counter({b.replace(old, new): c for b, c in sb.items()})
            msgs.append(f"reworded as registered: {old!r} -> {new!r} ({hits}x)")
        if sb == pb:
            return True, msgs + [f"OK: {sum(sb.values())} text blocks, identical (order not compared)."]
        msgs.append("MISMATCH (blocks, order not compared):")
        msgs += [f"  only in source: {b}" for b in sorted((sb - pb).elements())]
        msgs += [f"  only in port:   {b}" for b in sorted((pb - sb).elements())]
        return False, msgs

    src = page_words(source)
    for phrase in expect_removed:
        seq = phrase.split()
        src2, n = apply_seq(src, seq, [], exactly_once=True)
        if n != 1:
            return False, [f"ERROR: expected removal found {n} times in source (must be exactly 1): {phrase!r}"]
        src = src2
        msgs.append(f"removed as registered: {len(seq)} words ({' '.join(seq[:6])} ...)")
    for old, new in replace:
        src, n = apply_seq(src, old.split(), new.split(), exactly_once=False)
        if not n:
            return False, [f"ERROR: registry replacement not found in source (stale entry?): {old!r}"]
        msgs.append(f"reworded as registered: {old!r} -> {new!r} ({n}x)")
    port_words = page_words(port, ignore_class)
    if glossary_data:
        port_words += glossary_words(glossary_data)
    if src == port_words:
        return True, msgs + [f"OK: {len(src)} words, identical and in the same order."]
    msgs.append(f"MISMATCH: source {len(src)} words, port {len(port_words)} words.")
    msgs += list(difflib.unified_diff(src, port_words, "source", "port", lineterm="", n=4))
    return False, msgs


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source", nargs="?")
    ap.add_argument("port", nargs="?")
    ap.add_argument("--all", action="store_true", help="check every page listed in the registry")
    ap.add_argument("--no-registry", action="store_true", help="ignore the registered deviations (raw comparison)")
    ap.add_argument("--ignore-class", action="append", default=[])
    ap.add_argument("--unordered", action="store_true")
    ap.add_argument("--expect-removed", action="append", default=[])
    args = ap.parse_args()
    reg = json.load(open(REGISTRY, encoding="utf-8"))  # also the page list for --all

    jobs = []
    if args.all:
        for name, page in reg["pages"].items():
            jobs.append((os.path.join(reg["source_dir"], page["source"]), os.path.join(reg["port_dir"], name)))
    elif args.source and args.port:
        jobs.append((args.source, args.port))
    else:
        ap.error("give SOURCE PORT, or --all")

    failed = False
    for source, port in jobs:
        page = reg["pages"].get(os.path.basename(port), {})
        shared = reg.get("shared", {})
        if args.no_registry:  # raw comparison: keep only what's needed to compare at all
            page = {k: v for k, v in page.items() if k in ("unordered", "glossary_data")}
            shared = {}
        src_text = open(source, encoding="utf-8").read()
        # the shared rewording applies only to sources that carry the label
        replace = [pair for pair in shared.get("replace", []) if pair[0] in src_text]
        ok, msgs = check(source, port,
                         ignore_class=list(page.get("ignore_class", [])) + args.ignore_class,
                         expect_removed=list(page.get("expect_removed", [])) + args.expect_removed,
                         replace=replace,
                         unordered=page.get("unordered", False) or args.unordered,
                         glossary_data=page.get("glossary_data"))
        failed |= not ok
        if args.all:
            print(f"{'OK  ' if ok else 'FAIL'} {os.path.basename(port):26} {msgs[-1] if ok else ''}")
            if not ok:
                print("\n".join("     " + m for m in msgs))
        else:
            print("\n".join(msgs))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
