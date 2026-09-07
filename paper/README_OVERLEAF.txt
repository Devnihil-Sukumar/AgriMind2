AgriMind manuscript - Overleaf build instructions
=================================================

1. Go to overleaf.com -> New Project -> Upload Project
2. Upload AgriMind_paper.zip (this whole folder zipped)
3. Overleaf provides the elsarticle class natively - no extra setup needed
4. Set compiler to pdfLaTeX (Menu -> Compiler -> pdfLaTeX)
5. Compile. The bibliography is inline (thebibliography), so no BibTeX pass
   is required - a single pdfLaTeX run is enough, though run it twice so
   cross-references to tables/figures resolve.

BEFORE SUBMITTING - you must do these:
--------------------------------------
[ ] Add the 4 Amrita publication references (I could not access your
    intranet/Scopus repository, and did not invent them).
[ ] Verify all 16 existing reference entries against the PDFs in
    Refrence_paper/ - volume/page/author details were reconstructed from
    notes and need checking.
[ ] Replace author names, email and affiliation placeholders in the
    frontmatter.
[ ] Confirm the target journal - the class options at the top
    (preprint,12pt) may need changing to the journal's required format
    (e.g. final,5p,times for two-column).

Files
-----
Manuscript.tex          the paper
figures/                7 figures, 300 DPI
elsarticle-*.bst        bibliography styles (unused - bibliography is inline)
