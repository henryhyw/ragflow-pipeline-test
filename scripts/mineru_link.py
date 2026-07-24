"""Resolve footnotes/remarks in a MinerU content_list.json and emit linked chunks.

MinerU already handles the two things a generic parser cannot: it merges
cross-page tables and keeps merged-cell spans. What it does not do is connect a
reference such as "(1)" inside a table cell to its definition ("Note (1) : ...")
printed pages later. This does that, then writes the definitions into the object
that cites them so a downstream chunker keeps them together.

Usage:
    python mineru_link.py <mineru_out>/<stem>/txt/<stem>_content_list.json --out out/
"""
import argparse
import json
import re
from pathlib import Path

# a definition item: "Note (n)" / "Note<sup>(n)</sup>", optionally with a body
DEF_RE = re.compile(r"^\s*(?:note|remark)s?\s*(?:<sup>)?\(?(\d{1,2})\)?", re.I)
SUP_RE = re.compile(r"<sup>\(?(\d{1,2})\)?</sup>")
# a reference at the end of a table cell: "... etc. (1)"
CELL_REF_RE = re.compile(r"\((\d{1,2})\)\s*$")
CLEAN_TAGS = re.compile(r"</?sup>")


def _strip(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def load(path: str) -> list[dict]:
    return json.load(open(path, encoding="utf-8"))


def find_references(items: list[dict]) -> list[dict]:
    """Every (number, item-index) where a table cell cites a footnote."""
    refs = []
    for idx, it in enumerate(items):
        if it.get("type") != "table":
            continue
        for cell in re.findall(r"<td[^>]*>(.*?)</td>", it.get("table_body", ""), re.S):
            m = CELL_REF_RE.search(_strip(cell).strip())
            if m:
                refs.append({"number": int(m.group(1)), "item": idx,
                             "page": it.get("page_idx", 0)})
    return refs


def find_definitions(items: list[dict]) -> dict[int, dict]:
    """Map footnote number -> {text, page, item}. Stitches split bodies.

    MinerU sometimes emits the marker and the body as separate items
    (e.g. "Note(1)" then the sentence), and occasionally corrupts a label
    ("Note <sup>(8)</sup> ote (8)"). Both are repaired here by carrying an
    open definition forward until the next marker appears.
    """
    defs: dict[int, dict] = {}
    open_num = None
    for idx, it in enumerate(items):
        if it.get("type") != "text":
            continue
        raw = (it.get("text") or "").strip()
        m = SUP_RE.search(raw) or DEF_RE.match(raw)
        if m:
            num = int(m.group(1))
            body = CLEAN_TAGS.sub("", raw)
            body = re.sub(r"^\s*(?:note|remark)s?\s*\(?\d{1,2}\)?\s*(?:ote\s*\(\d+\))?",
                          "", body, flags=re.I).lstrip(" :：.-").strip()
            defs[num] = {"text": body, "page": it.get("page_idx", 0), "item": idx}
            open_num = num if not body else None       # body may be the next item
        elif open_num is not None and raw:
            # continuation of the previous marker-only definition
            joiner = "" if defs[open_num]["text"] else ""
            defs[open_num]["text"] = (defs[open_num]["text"] + joiner + raw).strip(" :：.-").strip()
            open_num = None
    return defs


def link(items):
    refs = find_references(items)
    defs = find_definitions(items)
    links, unresolved = [], []
    seen = set()
    for r in refs:
        d = defs.get(r["number"])
        if not d:
            unresolved.append(r)
            continue
        links.append({"number": r["number"], "ref_item": r["item"],
                      "ref_page": r["page"], "def_page": d["page"],
                      "span_pages": d["page"] - r["page"], "text": d["text"],
                      "id": f"fn-p{d['page'] + 1}-{r['number']}"})
        seen.add(r["number"])
    # definitions that were never cited from a table (e.g. (9)) still belong to
    # the table on the same run of pages; attach by proximity to the last table
    return links, unresolved, defs, seen


def emit(items, links, defs, seen):
    """Append each table's resolved notes to its HTML; drop standalone defs."""
    notes_for = {}
    for ln in links:
        notes_for.setdefault(ln["ref_item"], []).append((ln["number"], ln["text"]))
    # uncited definitions -> attach to the nearest preceding table
    table_indices = [i for i, it in enumerate(items) if it.get("type") == "table"
                     and it.get("table_body")]
    for num, d in defs.items():
        if num in seen:
            continue
        host = max((i for i in table_indices if i <= d["item"]), default=
                   (table_indices[0] if table_indices else None))
        if host is not None:
            notes_for.setdefault(host, []).append((num, d["text"]))

    def_items = {d["item"] for d in defs.values()}
    out = []
    for idx, it in enumerate(items):
        if idx in def_items:
            continue                                   # printed with its table
        if idx in notes_for and it.get("type") == "table":
            it = dict(it)
            notes = "".join(
                f'\n<p class="footnote" data-fn="fn-{n}">({n}) {t}</p>'
                for n, t in sorted(notes_for[idx]))
            it["table_body"] = it.get("table_body", "") + notes
            it["footnote_ids"] = [f"fn-{n}" for n, _ in sorted(notes_for[idx])]
        out.append(it)
    return out


def to_markdown(items) -> str:
    md = []
    for it in items:
        t = it.get("type")
        if t == "table":
            cap = " ".join(it.get("table_caption") or [])
            if cap:
                md.append(f"**{cap}**")
            md.append(it.get("table_body", ""))
        elif t in ("text", "header"):
            txt = re.sub(r"</?sup>", "", it.get("text") or "").strip()
            if txt:
                md.append(txt)
    return "\n\n".join(md)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("content_list")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()

    items = load(a.content_list)
    links, unresolved, defs, seen = link(items)
    linked = emit(items, links, defs, seen)

    outdir = Path(a.out); outdir.mkdir(parents=True, exist_ok=True)
    stem = Path(a.content_list).stem.replace("_content_list", "")
    (outdir / f"{stem}.linked.md").write_text(to_markdown(linked), encoding="utf-8")
    (outdir / f"{stem}.links.json").write_text(json.dumps({
        "references": len(find_references(items)),
        "definitions": len(defs),
        "linked": len(links),
        "cross_page": sum(1 for l in links if l["span_pages"]),
        "unresolved": unresolved,
        "links": links,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{stem}: refs={len(find_references(items))} defs={len(defs)} "
          f"linked={len(links)} cross_page={sum(1 for l in links if l['span_pages'])} "
          f"unresolved={len(unresolved)}")
    print(f"  -> {outdir / (stem + '.linked.md')}")
    print(f"  -> {outdir / (stem + '.links.json')}")


if __name__ == "__main__":
    main()
