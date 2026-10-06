"""Check that a ported business-models page kept every word of its approved source.

Compares the visible text of a Claude Design export (Output/business-models-source/
*.dc.html) with its port in business-models/, in document order. Formatting,
markup and whitespace are ignored; any added, dropped or changed word is reported.
Text the port adds on purpose (e.g. matrix row labels repeated inside each cell for
phones) is excluded with --ignore-class. Text the port drops on purpose (e.g. the model
cards' in-page stepper, replaced by the shared header) is declared with --expect-removed:
that exact word sequence must occur exactly once in the source, and is removed from the
source before comparing. Anything else that differs still fails.

Usage:
    python tools/check_port_text.py Output/business-models-source/Main.dc.html \
        business-models/index.html --ignore-class cell-label
    python tools/check_port_text.py Output/business-models-source/Mallikortti2.dc.html \
        business-models/gpu-cloud.html --expect-removed "AI OY:N KASVUPOLKU 1 Julkinen pilvi ..."

Exit code 0 when the texts match, 1 when they differ.
"""
import argparse
import difflib
import sys
from html.parser import HTMLParser

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


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source")
    ap.add_argument("port")
    ap.add_argument("--ignore-class", action="append", default=[],
                    help="class of elements whose text the port adds on purpose (repeatable)")
    ap.add_argument("--unordered", action="store_true",
                    help="compare text blocks as a multiset, ignoring order (for canvas sources whose "
                         "DOM order differs from reading order, e.g. Arvoketju)")
    ap.add_argument("--expect-removed", action="append", default=[],
                    help="word sequence the port drops on purpose; must occur exactly once in the source (repeatable)")
    args = ap.parse_args()

    if args.unordered:
        from collections import Counter
        sb, pb = Counter(parse(args.source).blocks()), Counter(parse(args.port, args.ignore_class).blocks())
        if sb == pb:
            print(f"OK: {sum(sb.values())} text blocks, identical (order not compared).")
            return 0
        print("MISMATCH (blocks, order not compared):")
        for b in sorted((sb - pb).elements()):
            print("  only in source:", b)
        for b in sorted((pb - sb).elements()):
            print("  only in port:  ", b)
        return 1

    src = page_words(args.source)
    for phrase in args.expect_removed:
        seq = phrase.split()
        hits = [i for i in range(len(src) - len(seq) + 1) if src[i:i + len(seq)] == seq]
        if len(hits) != 1:
            print(f"ERROR: expected removal found {len(hits)} times in source (must be exactly 1): {phrase!r}")
            return 1
        del src[hits[0]:hits[0] + len(seq)]
        print(f"removed as declared: {len(seq)} words ({' '.join(seq[:6])} ...)")
    port = page_words(args.port, args.ignore_class)
    if src == port:
        print(f"OK: {len(src)} words, identical and in the same order.")
        return 0
    print(f"MISMATCH: source {len(src)} words, port {len(port)} words.")
    for line in difflib.unified_diff(src, port, "source", "port", lineterm="", n=4):
        print(line)
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
