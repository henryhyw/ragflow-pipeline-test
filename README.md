# Document to chunks: a RAGFlow pipeline test

A 5-page document taken through parsing, footnote linking, chunking and retrieval,
to see whether a footnote printed pages away from the table that cites it can be
kept with that table all the way into a retrieved chunk.

**[Read the walkthrough](https://henryhyw.github.io/ragflow-pipeline-test/)**

## What is being tested

The document was written to contain six things a pipeline has to survive:

| Test | Where it is |
|---|---|
| Merged cells | Four full-width section rows, seven cells spanning 2 to 4 rows |
| A table split across a page break | Table 1 runs from page 2 to page 3 |
| A footnote whose definition is pages away | 13 references on pages 2 and 3, all 10 definitions on page 4 |
| A paragraph split across a page break | Section 2, across pages 1 and 2 |
| Page furniture | Running header and page number on all 5 pages |
| A flowchart | Figure 1 on page 5, with labels that exist only as pixels |

## Result

Parsing kept the merged cells, joined the two halves of the table, rejoined the split
paragraph, labelled the furniture separately, and extracted the figure. The linking
step resolved all 13 references, every one of them across a page boundary, with none
left unresolved.

The same parse was then rendered twice, once with the linking applied and once
without, and both were uploaded to the same knowledge base. Of the nine chunks
returned across both retrieval tests, one contains the table row and the condition
that governs it together, and it is the top hit in the linked base.

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
