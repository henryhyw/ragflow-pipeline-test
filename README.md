# From PDF to retrieved chunk: testing a RAGFlow ingestion pipeline

Whether merged tables, cross-page footnotes, page breaks and flow charts survive
from PDF to retrieved chunk. Tested end to end through MinerU parsing, a custom
linking step, and RAGFlow chunking, embedding and retrieval.

**[Read the walkthrough](https://henryhyw.github.io/ragflow-pipeline-test/)**

## What was tested

| Problem | Result | What happened |
|---|---|---|
| Tables with merged cells | Held | Four full-width rows and seven cells spanning 2 to 4 rows kept their `colspan` and `rowspan` |
| Nested tables | **Not tested** | The test document has no table inside a table cell |
| Remarks and footnotes across pages | Held, with a custom step | 13 references resolved, every one across a page boundary, none unresolved. Needs a step RAGFlow does not provide |
| Page breaks | Held | A paragraph and a table each split across pages came back whole. Repeated headers and page numbers typed separately |
| Flow charts | Extracted, retrieval not tested | Came out as an image object with its caption. The vector is built from the caption, not the picture |

## What it comes down to

The only gap is deterministic rather than a model problem: everything except the
footnote connection is handled by parsing and by RAGFlow, and the connection itself
is about thirty lines of rule-based code.

The gain is what a single chunk is sufficient for, not the ranking. Of the nine
results returned across both retrieval tests, exactly one contains the table row and
the condition that governs it, and it is the top hit after linking. The ranking gain
alone is 1.63 points.

## Contents

| Path | What it is |
|---|---|
| `index.html` | The walkthrough. Self-contained, no network needed |
| `test-document.pdf` | The 5-page source document |
| `outputs/linked.md` | Parsed output with each definition written into the table that cites it |
| `outputs/unlinked.md` | The same parse without the linking, for comparison |
| `outputs/links.json` | Every resolved reference with its page span |
| `outputs/mineru_content_list.json` | Raw MinerU output |
| `scripts/mineru_link.py` | The linker |
| `scripts/make_pair.py` | Produces the linked and unlinked pair from one parse |

## Reproducing

```bash
uv venv --python 3.12 ~/mineru-venv
uv pip install --python ~/mineru-venv/bin/python "mineru[core]==3.4.4"

~/mineru-venv/bin/mineru -p test-document.pdf -o mineru_out -m txt -b pipeline -d cpu
python scripts/make_pair.py mineru_out/test-document/txt/test-document_content_list.json --out demo_out
```

The `[core]` extra matters. The bare `mineru` package does not pull in torch, and the
pipeline backend fails at import without it.

Expected output:

```
refs=13 defs=10 linked=13 cross_page=13 unresolved=0
```

## Notes

The document is synthetic. It imitates the structure of a technical circular but
contains no real regulation and no material from any organisation.

Versions: MinerU 3.4.4 (pipeline backend, CPU), RAGFlow with `jina-embeddings-v4`.
Run 24 July 2026.
