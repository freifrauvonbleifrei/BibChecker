# BibChecker
Analyzes IEEE and ACM format bibliographies for correctness.  Only to be used as a first pass.  Anything that cannot be found automatically should be checked by hand.

## Checking Citations in a PDF
`python3 -m bibcheck.main filename.pdf`

## Available Command Line Arguments
`-ieee` : Assume IEEE-formatted bibliography (default)
`-siam` : Assume SIAM-formatted bibliography
`-acm` : Assume ACM-formatted bibliophgray

