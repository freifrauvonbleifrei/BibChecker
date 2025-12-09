import re
import feedparser
from urllib.parse import quote_plus

from .validate import Validate
from .utils import exclusions, normalize_title, normalize_hyphen_title, normalize_entry, format_for_url, normalize_authors


class Citation:
    def __init__(self, number, entry, args):
        self.match_percent = 0
        self.match_title = None
        self.number = number

        self.entry = normalize_entry(entry)

        self.excluded = False
        lower = format_for_url(self.entry)
        for pattern, label in exclusions.items():
            if pattern in lower:
                self.excluded = True
                return

        # Find DOI
        self.doi = None
        self.arxiv_id = None
        doi_entry = re.sub(r'\.\s*\n\s*(\d)', r'.\1', entry)
        doi_match = re.search(r"(10\.\d{4,9}/[^\s\"<>]+)", doi_entry)
        if doi_match:
            self.doi = doi_match.group(1).rstrip('.,;)')
        else:
            # Find ArXiv 
            m = re.search(
                r"(?:arXiv\s*:\s*|https?://arxiv\.org/abs/)"
                r"([0-9]{4}\.[0-9]{4,5}(?:v\d+)?|[a-z\-]+/\d{7}(?:v\d+)?)",
                entry,
                re.I,
            )
            if m:
                self.arxiv_id = m.group(1)


        # Split into title, author, venue
        m = None
        if args.acm:
            pattern = r'^(?P<authors>.+?)\.\s*(?P<year>(19|20)\d{2})\.\s*(?P<title>.+?)(?=\. )'
        elif args.siam:
            pattern = r'^(?P<authors>.+?)\.\s+(?P<title>.+?)\.\s+.*?(?P<year>(19|20)\d{2})\b'
        else:
            pattern = r'^(?P<authors>.*?)["“”](?P<title>.+?)["“”]'

        m = re.search(pattern, entry, re.DOTALL)

        # If title/authors/etc not found, try other patterns
        if not m:
            pattern = r'^(?P<authors>.*?)["“”](?P<title>.+?)["“”]'
            m = re.search(pattern, entry, re.DOTALL)

        ## Try author, year, title
        if not m:
            pattern = r'''
                ^(?P<authors>.+?)          # authors (non-greedy)
                [\.,]\s*                   # dot or comma after authors
                (?P<year>(19|20)\d{2})     # four-digit year
                [\.,]\s*                   # dot or comma after year
                (?P<title>.+?)$            # remainder = title
            '''
            m = re.search(pattern, entry, re.DOTALL | re.VERBOSE)

        ## Try authors, title, year with multiple authors
        if not m:
            pattern = r'''
                ^(?P<authors>
                    .*?                  # anything up to the first ' and ' or ', and '
                    (?:[ ,]and )         # space-or-comma, then 'and', then space
                    .*?                  # rest of the authors (can include periods for initials)
                    \b[A-Za-z]{2,}       # final word before separator: >= 2 letters (e.g. 'Bienz')
                )
                [\.,]\s*                 # consume the punctuation right after authors
                (?P<title>
                    [^.]+?               # title: any chars except '.' (no periods allowed in title)
                )
                [\.,]\s*                 # punctuation right after title
                (?P<year>(19|20)\d{2})\b
                .*$
            '''
            m = re.search(pattern, entry, re.DOTALL | re.VERBOSE) 

        ## Try authors, title (no year) with multiple authors
        if not m:
            pattern = r'''
                ^(?P<authors>
                    .*?
                    (?:[ ,]and )
                    .*?
                    \b[A-Za-z]{2,}
                )
                [\.,]\s*
                (?P<title>
                    [^.]*[A-Za-z][^.]*?  # within the title (before the next .),
                                         # must have at least one letter
                )
                [\.,]\s*
                .*$
            '''
            m = re.search(pattern, entry, re.DOTALL | re.VERBOSE)    
        ## Try author, title, year (single author)
        if not m:
            pattern = r'''
                ^
                (?P<authors>
                    (?:                             # consume chars that are NOT the boundary start
                        (?!\b[A-Za-z]{2,}[\.,])     # don't step over a WORD{2,} + . or , boundary
                        .                           # consume one char
                    )*
                    \b[A-Za-z]{2,}                  # final word before separator: >= 2 letters
                )
                (?=[\.,])                           # next char must be . or ,
                [\.,]\s*                            # consume the punctuation
                (?P<title>\s*
                    [^.]+?                          # title (no periods allowed)
                )
                [\.,]\s*
                (?P<year>(19|20)\d{2})\b
                .*$
            '''      
            m = re.search(pattern, entry, re.DOTALL | re.VERBOSE)  

        ## Try author, title (no year) for a single author
        if not m:
            pattern = r'''
                ^
                (?P<authors>
                    (?:                             # consume chars that are NOT the boundary start
                        (?!\b[A-Za-z]{2,}[\.,])     # don't step over a WORD{2,} + . or , boundary
                        .                           # consume one char
                    )*
                    \b[A-Za-z]{2,}                  # final word before separator: >= 2 letters
                )
                (?=[\.,])                           # next char must be . or ,
                [\.,]\s*                            # consume the punctuation
                (?P<title>\s*
                    [^.]+?                          # title (no periods allowed)
                )
                [\.,]\s*
                .*$
            '''       
            m = re.search(pattern, entry, re.DOTALL | re.VERBOSE) 

        if not m:
            pattern = r'''
                ^(?P<authors>.+?)          # authors (non-greedy)
                [\.,]\s*                   # dot or comma after authors
                (?P<title>[^.]+?)            # remainder = title
                [\.,]\s*                   # dot or comma after year
                .*$
            '''
            m = re.search(pattern, entry, re.DOTALL | re.VERBOSE)

        self.title = None
        self.authors = None
        if m:
            self.title = m.group("title").strip(' ,')

            self.authors = m.group("authors").strip(" ,")
            self.authors = normalize_entry(self.authors)

            year_match = re.search(r'(?<![\d/])\b(19|20)\d{2}\b(?![\d/])', self.title)
            if year_match:
                year = year_match.group(0)
                self.title = self.title.replace(year, '')

                    
        self.norm_title = None
        self.norm_hyphen_title = None
        if self.title:
            self.norm_title = normalize_title(self.title)
            self.norm_hyphen_title = normalize_hyphen_title(self.title)

    def validate(self):
        if self.excluded:
            return

        validation = Validate(self)
        if validation.score_title != 1.0:
            print("\n")
            print("\n")
            print(self.number, self.entry)
            print("Titles do not match!")
            if self.doi:
                print("DOI NOT A MATCH! ", self.doi)
            elif self.arxiv_id:
                print("ARXIV ID NOT A MATCH! ", self.arxiv_id)
            print(self.title)
            print(self.norm_title)
            print(validation.title)
        else:
            validation.compare_authors(self)
            if validation.score_authors < 0.9:
                print("\n")
                print("\n")
                print(self.number, self.entry)
                print("Authors do not match!")
                print(self.authors)
                print(validation.authors)

