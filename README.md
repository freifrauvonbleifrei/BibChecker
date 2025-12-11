# BibChecker
Analyzes IEEE, SIAM, and ACM format bibliographies for correctness.  The tool parses an input PDF and checks the correctness of DOI links, ArXiv IDs, titles, and authors against online metadata.  Currently, the tool searches OpenAlex, Citeseer, Arxiv, Googlebooks, DBLP, and OSTI's openly available APIs.  This citation checker performs python string comparisons.  **No generative AI tools are used when running this tool, allowing for it to be run during the paper review process.** This tool is only intended to be used as a first pass, not to replace human reviews.  Please verify all output for false positives.

## Checking Citations in a PDF
`python3 -m bibcheck.main filename.pdf`

## Available Command Line Arguments
`-ieee` : Assume IEEE-formatted bibliography (default)
`-siam` : Assume SIAM-formatted bibliography
`-acm` : Assume ACM-formatted bibliophgray

*Acknowledgement: ChatGPT was used to generate string comparison patterns.*
