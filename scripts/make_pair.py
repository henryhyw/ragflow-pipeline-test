"""Produce the before/after Markdown pair for the demo, from one MinerU parse.

Both files are rendered by the same function from the same content_list.json, so
the only difference between them is the footnote linking. Anything that shows up
in a diff is attributable to the linker and to nothing else.

    python demo_make_pair.py mineru_demo/demo_pipeline_test_doc/txt/demo_pipeline_test_doc_content_list.json --out demo_out

Writes:
    <stem>.baseline.md   MinerU output, footnotes left where they were printed
    <stem>.linked.md     same content, footnote definitions moved into the table
    <stem>.report.json   counts, and every link with its page span
    <stem>.excerpt.txt   the one table row and note that make the point, side by side
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "footnote_linker"))
import mineru_link as ml


def render(items) -> str:
    """Render content_list items to Markdown.

    Two departures from mineru_link.to_markdown, both found by running this on
    the real parse rather than by reading the code:

    Images are rendered. to_markdown handles text, headers and tables only, so
    an image item is dropped, which would have deleted Figure 1 silently.

    Items typed "header" are skipped. In MinerU that type is the running page
    header, not a section heading, so including it repeats the masthead once per
    page inside the text that gets chunked and embedded. Section headings arrive
    as ordinary text carrying a text_level, and are rendered from that instead.
    """
    out = []
    for it in items:
        t = it.get("type")
        if t == "table":
            cap = " ".join(it.get("table_caption") or [])
            if cap:
                out.append(f"**{cap}**")
            body = it.get("table_body") or ""
            if body:
                out.append(body)
        elif t == "image":
            cap = " ".join(it.get("image_caption") or []).strip()
            out.append(f"![{cap}]({it.get('img_path', '')})")
            if cap:
                out.append(f"*{cap}*")
        elif t == "text":
            txt = re.sub(r"</?sup>", "", it.get("text") or "").strip()
            if not txt:
                continue
            level = it.get("text_level")
            out.append(f"{'#' * min(int(level), 6)} {txt}" if level else txt)
        # "header" and "page_number" are page furniture and are dropped
    return "\n\n".join(out)


FOOTNOTE_P = re.compile(r'<p class="footnote" data-fn="fn-(\d+)">.*?</p>', re.S)


def dedupe_notes(items):
    """Drop repeated footnote paragraphs inside one table.

    emit() appends one paragraph per resolved link, and a footnote cited from two
    different rows resolves twice, so notes (5), (8) and (10) each landed in the
    table twice with identical text. The reference count is still right, and is
    still reported, but the table should carry each definition once.
    """
    out = []
    for it in items:
        body = it.get("table_body")
        if not body or "footnote" not in body:
            out.append(it)
            continue
        seen = set()

        def keep(m):
            n = m.group(1)
            if n in seen:
                return ""
            seen.add(n)
            return m.group(0)

        it = dict(it)
        it["table_body"] = re.sub(r"\n?" + FOOTNOTE_P.pattern, keep, body, flags=re.S)
        out.append(it)
    return out


def excerpt(baseline: str, linked: str, number: int = 4) -> str:
    """Show the citing cell and the note text in each file, so the change is visible.

    The whole table is far too wide to read on a slide, so this pulls out only
    the cell that cites the footnote, the standalone definition line, and the
    footnote paragraph the linker appends.
    """
    def cited_cell(md: str) -> str:
        for cell in re.findall(r"<td[^>]*>(.*?)</td>", md, re.S):
            text = re.sub(r"<[^>]+>", "", cell).strip()
            if text.endswith(f"({number})"):
                return text
        return "(citing cell not found)"

    def standalone_note(md: str) -> str:
        for line in md.splitlines():
            if re.match(rf"^\s*Note\s*\({number}\)", line, re.I):
                return line.strip()
        return "(no standalone note line)"

    def attached_note(md: str) -> str:
        m = re.search(rf'<p class="footnote" data-fn="fn-{number}">(.*?)</p>', md, re.S)
        return m.group(1).strip() if m else "(no note attached to the table)"

    return (
        f"Footnote ({number})\n"
        f"{'=' * 60}\n\n"
        "BEFORE, as MinerU parsed it\n"
        f"{'-' * 60}\n"
        f"  table cell   : {cited_cell(baseline)}\n"
        f"  note text    : {standalone_note(baseline)}\n"
        f"  attached?    : {attached_note(baseline)}\n\n"
        "AFTER, once the linker has run\n"
        f"{'-' * 60}\n"
        f"  table cell   : {cited_cell(linked)}\n"
        f"  note text    : {standalone_note(linked)}\n"
        f"  attached?    : {attached_note(linked)}\n\n"
        "The note moves out of the page it was printed on and into the table\n"
        "object that cites it, so the chunker cannot separate them.\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("content_list")
    ap.add_argument("--out", default="demo_out")
    ap.add_argument("--excerpt-note", type=int, default=4,
                    help="footnote number to show side by side")
    a = ap.parse_args()

    items = ml.load(a.content_list)
    links, unresolved, defs, seen = ml.link(items)
    linked_items = dedupe_notes(ml.emit(items, links, defs, seen))

    baseline_md = render(items)
    linked_md = render(linked_items)

    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = Path(a.content_list).stem.replace("_content_list", "")

    (outdir / f"{stem}.baseline.md").write_text(baseline_md, encoding="utf-8")
    (outdir / f"{stem}.linked.md").write_text(linked_md, encoding="utf-8")
    (outdir / f"{stem}.excerpt.txt").write_text(
        excerpt(baseline_md, linked_md, a.excerpt_note), encoding="utf-8")

    n_images = sum(1 for it in items if it.get("type") == "image")
    n_tables = sum(1 for it in items if it.get("type") == "table")
    report = {
        "source": a.content_list,
        "pages": max((it.get("page_idx", 0) for it in items), default=-1) + 1,
        "tables": n_tables,
        "images": n_images,
        "references": len(ml.find_references(items)),
        "definitions": len(defs),
        "linked": len(links),
        "cross_page": sum(1 for l in links if l["span_pages"]),
        "distinct_notes_attached": len({l["number"] for l in links}),
        "unresolved": unresolved,
        "links": links,
    }
    (outdir / f"{stem}.report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{stem}: pages={report['pages']} tables={n_tables} images={n_images}")
    print(f"  refs={report['references']} defs={report['definitions']} "
          f"linked={report['linked']} cross_page={report['cross_page']} "
          f"unresolved={len(unresolved)}")
    if unresolved:
        print(f"  UNRESOLVED: {unresolved}")
    for p in ("baseline.md", "linked.md", "excerpt.txt", "report.json"):
        print(f"  -> {outdir / (stem + '.' + p)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
