import re
import json
import sys
import time
import unicodedata
from PyPDF2 import PdfReader
from habanero import Crossref
import feedparser
import requests
import string
import unicodedata
import html
import csv
from urllib.parse import quote_plus
import requests
from requests.exceptions import Timeout
from httpx import HTTPStatusError
from time import sleep
from urllib.parse import urlparse
import arxiv
import Levenshtein



cr = Crossref(timeout=30)
client = arxiv.Client()

class Citation:
    def __init__(self, number, entry):
        self.match = False
        self.match_percent = 0

        self.number = number

        self.title = None
        self.authors = None
        self.venue = None
        self.url = None
        self.doi = None
        self.url_exists = None
        self.id_match = None

        author_block = None
        self.arxiv_id = None

        self.match_title = None
        self.match_authors = None
        self.match_percent = 0
        self.match_venue = None
        self.match_url = None


        # Find URL, if one is included
        url_match = re.search(r"(https?://[^\s]+(?:\s*[^\s]+)*)", entry, re.MULTILINE)
        if url_match:
            self.url = url_match.group(1).replace("\n", "").replace(" ", "")
        elif "arxiv" in entry:
            m = re.search(
                r"(?:arXiv\s*:\s*|https?://arxiv\.org/abs/)"
                r"([0-9]{4}\.[0-9]{4,5}(?:v\d+)?|[a-z\-]+/\d{7}(?:v\d+)?)",
                entry,
                re.I,
            )
            if m:
                self.arxiv_id = m.group(1)
                self.url = f"https://arxiv.org/abs/{arxiv_id}"

        # Find DOI, if one is included
        doi_match = re.search(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", entry, re.IGNORECASE)
        if doi_match:
            self.doi = doi_match.group(1)
            if not self.url:
                self.url = f"https://doi.org/{self.doi}"

        entry = unicodedata.normalize("NFKC", entry)
        entry = re.sub(r'\s*([\u0300-\u036F])\s*', r'\1', entry)
        entry = unicodedata.normalize("NFC", entry)
        entry = entry.replace('-\n', '')
        entry = entry.replace('\n', ' ')
        entry = entry.replace(', et al', '')
        entry = entry.replace('et al', '')
        self.entry = entry

        # Split into title, author, venue
        m = re.search(
            r'^(.*?)["“”](.+?)["“”]',
            entry,
            re.DOTALL | re.UNICODE
        )
        if m:
            author_block = m.group(1).strip(" ,")
            self.title = m.group(2).strip()
        else:
            m = entry.split('.')

            authors = ""
            title = ""
            split = False
            for fragment in m:
                names = fragment.split(', ')
                for name in names:
                    if not split:
                        auths = True 
                        split_and = name.split('and')
                        for word in split_and:
                            if len(word.split()) > 2:
                                auths = False
                                break
                        if auths:
                            authors += name
                        elif re.search(r"\b[A-Z]\s?\.", name):
                            authors += name
                        elif re.search(r"(^|\s)(?![IA](\s|$))[A-Z](\s|$)", name): # Middle Initial, forgot the period
                            print(name)
                            authors += name
                        else:
                            split = True
                            title += name
                    else:
                        if name.split()[0] in ["in Proceeding", "pages", "pp", "sec", "vol", "Vol", "Sec", "Pages", "volume"]:
                            break
                        title += name
                if split:
                    break

            year_match = re.search(r',\s*(\d{4})$', title)
            if year_match:
                year = year_match.group(1)
                title = title.replace(year, '')
            title = title.split('?')[0]
            author_block = authors

            self.title = title



        self.title = self.title.rstrip(' ,')
        

        ## Split authors into list of lowercase last names
        if author_block:
            self.authors = list()
            author_block = normalize_text(author_block)
            raw_authors = re.split(r",| and ", author_block)
            for a in raw_authors:
                a = a.strip()
                if not a:
                    continue
                surname = a.split()[-1].strip(string.punctuation)
                self.authors.append(surname)
        
        self.norm_title = None
        self.norm_hypen_title = None
        if self.title:
            self.norm_title = normalize_text(self.title)
            self.norm_hyphen_title = normalize_hyphen_text(self.title)



        lower = self.entry.lower()
        lower = lower.replace('\n', '')
        lower = lower.replace(' ', '')

        if "github.com" in lower:
            self.match_percent = 0.99
            self.match_title = "GitHub Repository"
        elif "https://gitlab" in lower:
            self.match_percent = 0.99
            self.match_title = "GitLab Repository"
        elif "docs.amd.com" in lower:
            self.match_percent = 0.99
            self.match_title = "AMD Docs"
        elif "developer.nvidia.com" in lower:
            self.match_percent = 0.99
            self.match_title = "NVIDIA Docs"
        elif ".pdf" in lower:
            self.match_percent = 0.99
            self.match_title = "Included .pdf Link"
        elif "ofiwg.github.io" in lower:
            self.match_percent = 0.99
            self.match_title = "Libfabric"
        elif "www.kernel.org" in lower:
            self.match_percent = 0.99
            self.match_title = "Linux"
        elif "gnuplot.sourceforge.net" in lower:
            self.match_percent = 0.99
            self.match_title = "GNUPlot"
        elif "mvapich.cse.ohio-state.edu" in lower:
            self.match_percent = 0.99
            self.match_title = "MVAPICH"
        elif "lapackuser" in lower and "guide" in lower:
            self.match_percent = 0.99
            self.match_title = "LAPACK"
        elif "huggingface" in lower:
            self.match_percent = 0.99
            self.match_title = "Huggingface"
        elif "https" in lower and "blog" in lower:
            self.match_percent = 0.99
            self.match_title = "Blog Post"
        elif "top500.org" in lower:
            self.match_percent = 0.99
            self.match_title = "Top 500"
        elif "docs.nersc.gov" in lower:
            self.match_percent = 0.99
            self.match_title = "NERSC"
        elif "nasparallelbenchmarks" in lower:
            self.match_percent = 0.99
            self.match_title = "NAS"
        elif "valgrind.org" in lower:
            self.match_percent = 0.99
            self.match_title = "Valgrind"
        elif "mpistandard" in lower or "mpi:amessagepassinginterface" in lower:
            self.match_percent = 0.99
            self.match_title = "MPI"
        elif "doku.lrz.de" in lower:
            self.match_percent = 0.99
            self.match_title = "Leibniz Supercomputing"
        elif "aws.amazon.com" in lower:
            self.match_percent = 0.99
            self.match_title = "AWS"


    def validate(self):
        if not self.title:
            return


        if self.arxiv_id:
            self.check_arxiv_link()
        if self.match_percent == 1.0:
            return
        
        if self.doi:
            if "10.5281" in self.doi:
                self.check_datacite_doi()
            else:
                self.check_doi()
        if self.match_percent == 1.0:
            return

        self.search_openalex(self.title)
        if self.match_percent == 1.0:
            return

        self.search_openalex(self.norm_title)
        if self.match_percent == 1.0:
            return

        self.search_openalex(self.norm_hyphen_title)
        if self.match_percent == 1.0:
            return

        self.search_arxiv(self.norm_title)
        if self.match_percent == 1.0:
            return

        self.search_arxiv(self.norm_hyphen_title)
        if self.match_percent == 1.0:
            return

        self.search_googlebooks(self.norm_title)
        if self.match_percent == 1.0:
            return

        self.search_googlebooks(self.norm_hyphen_title)
        if self.match_percent == 1.0:
            return

        self.search_crossref(self.norm_title)
        if self.match_percent == 1.0:
            return

        self.search_crossref(self.norm_hyphen_title)
        if self.match_percent == 1.0:
            return

    def sequence_similarity(self, found):
        norm_found = normalize_text(found)

        score = max(Levenshtein.ratio(self.norm_title, norm_found),
                   Levenshtein.ratio(self.norm_hyphen_title, norm_found))

        if ":" in self.title:
            score = max(score, Levenshtein.ratio(normalize_text(self.title.split(':')[0]), norm_found))

        return score

    def compare(self, title, authors, venue, url):
        if not title:
            return

        match_percent = self.sequence_similarity(title)

        if (match_percent > self.match_percent):
            self.match_percent = match_percent
            self.match_title = title
            self.match_authors = authors
            self.match_venue = venue
            self.match_url = url

        return match_percent

    def check_arxiv_link(self):
        api_url = f"http://export.arxiv.org/api/query?id_list={self.arxiv_id}"
        try:
            feed = feedparser.parse(api_url)
            if not feed.entries:
                self.id_match = 0
                return

            arxiv_entry = feed.entries[0]
            title = arxiv_entry.get("title", "").strip()
            authors = [a.name for a in arxiv_entry.get("authors", [])]
            self.doi_title = title
            self.id_match = self.compare(title, authors, "arXiv", api_url);
        except Timeout:
            print("Arxiv Link timeout on url, retrying", api_url)
            sleep(2)
            self.check_arxiv_link()


    def check_doi(self):
        try:
            result = cr.works(ids=self.doi)
            authors = []
            for a in result["message"].get("author", []):
                name = a.get("family") or a.get("name") or ""
                if a.get("given"):
                    name = f"{a['given']} {name}".strip()
                if name:
                    authors.append(name)
            title = result["message"].get("title", [""])[0]
            venue = ""
            if result["message"].get("container-title"):
                venue = result["message"].get("container-title", [""])[0]
            self.doi_title = title
            self.id_match = self.compare(title, authors, venue, None)
        except RuntimeError as e:
            if "timed out" in str(e).lower():
                print("Crossref DOI timeout, retrying", self.doi)
                sleep(2)
                self.check_doi()
            else:
                raise
        except Timeout:
            print("Crossref DOI timeout, retrying", self.doi)
            sleep(2)
            self.check_doi()
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                self.doi_exists = False
                self.id_match = 0

    def check_datacite_doi(self):
        api_url = f"https://api.datacite.org/dois/{self.doi}"
        try:
            r = requests.get(api_url, timeout=20)
            if r.status_code == 200:
                data = r.json()["data"]["attributes"]

                # Extract title
                title = data.get("titles", [{}])[0].get("title", "")

                # Extract authors
                authors = []
                for c in data.get("creators", []):
                    if "givenName" in c and "familyName" in c:
                        authors.append(f"{c['givenName']} {c['familyName']}".strip())
                    else:
                        authors.append(c.get("name", ""))
                
                # Extract venue (publisher for datasets)
                venue = data.get("publisher", "")

                self.doi_title = title
                self.id_match = self.compare(title, authors, venue, None)
            else:
                print(f"DataCite DOI not found: {self.doi}")
                self.id_match = 0
        except requests.RequestException as e:
            print("DataCite error:", e)
            self.id_match = 0
        
    def search_crossref(self, title):
        try:
            result = cr.works(query = title, limit = 10)
            items = result.get("message", {}).get("items", [])
            for item in items:
                title = item.get("title", [""])[0]
                authors = [a.get("family", "").lower() for a in item.get("author", [])]
                venue = ""
                if item.get("container-title"):
                    venue = item.get("container-title", [""])[0]
                self.compare(title, authors, venue, None)
                if self.match_percent >= 0.99:
                    break
        except Timeout:
            print("Crossref timeout, retrying")
            sleep(2)
            self.search_crossref(title)
        except RuntimeError as e:
            if "timed out" in str(e).lower():
                print("Crossref timeout, retrying")
                sleep(2)
                self.search_crossref(title)
            else:
                raise


    def search_openalex(self, title):    
        query = quote_plus(title)
        url = f"https://api.openalex.org/works?search={query}&per-page=10"
        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                print(f"OpenAlex search failed ({r.status_code}): {url}")
                return

            data = r.json()
            results = data.get("results", [])

            # iterate over the top 10 results
            for i, work in enumerate(results[:10], start=1):
                title = work.get("title", "")
                authors = [a["author"]["display_name"] for a in work.get("authorships", [])]
                venue = work.get("host_venue", {}).get("display_name", "")
                link = work.get("id")  # canonical OpenAlex work ID URL

                # compare against your reference
                self.compare(title, authors, venue, link)

                if self.match_percent >= 0.99:
                    return

        except requests.exceptions.Timeout:
            print("OpenAlex timeout, retrying", url)
            sleep(2)
            self.search_openalex(title)  # pass title again to retry

        except Exception as e:
            print("OpenAlex search error:", e)


    def search_arxiv(self, title):
        try:
            search = arxiv.Search(
                query=title,
                max_results=10,
                sort_by=arxiv.SortCriterion.Relevance
            )

            client = arxiv.Client()   # new style API
            for result in client.results(search):
                title = result.title
                authors = [str(a) for a in result.authors]
                link = result.entry_id  # stable arXiv URL
                self.compare(title, authors, "arXiv", link)

                if self.match_percent >= 0.99:
                    break

        except Exception as e:
            print("arXiv search error:", e)



    def search_googlebooks(self, title):
        url = f"https://www.googleapis.com/books/v1/volumes?q={title}"
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                data = r.json()
                for item in data.get("items", []):
                    info = item.get("volumeInfo", {})
                    title = info.get("title") or ""
                    authors = info.get("authors", [])
                    publisher = info.get("publisher", "")
                    self.compare(title, authors, publisher, url)
        except requests.exceptions.Timeout:
            print("Googlebooks timeout on url, retrying", url)
            sleep(2)
            self.search_googlebooks(title)


    def write_to_csv(self, writer):
        writer.writerow([self.number, self.match_percent, self.id_match, self.url_exists, self.url, self.title, self.match_title, self.authors, self.match_authors, self.match_url, self.entry])

    def write_to_stdout(self):
        if self.match_percent >= 0.99:
            color = "\033[92m"   # green
        else:
            color = "\033[91m"   # red

        print(color + self.number, self.entry, "Closest Match: ", self.match_title, self.match_authors)
        print('\n')

    def write_not_found(self):
        if self.match_percent < 0.99:
            print(self.number, self.entry, "Closest Match: ", self.match_title, self.match_authors)
            print(self.title)
            print('\n')

class Bibliography:
    bib_text = ""
    entries = ""
    bib_format = ""

    def __init__(self, bib_format = "ieee"):
        self.bib_format = bib_format.lower()
        self.entries = list()
        self.bib_text = ""

    def parse_acm(self):
        entries = re.split(r"\[\d+\]", self.bib_text)
        for i, entry in enumerate(entries, 1):
            clean = " ".join(entry.split()).strip()
            if not clean:
                continue
            self.entries.append(Citation(i, entry))

    def parse_ieee(self):
        pattern = r"\[(\d+)\]\s*(.+?)(?=\[\d+\]|\Z)"
        entries = re.findall(pattern, self.bib_text, re.DOTALL)
        for i, entry in entries:
            clean = " ".join(entry.split()).strip()
            if not clean:
                continue
            self.entries.append(Citation(i, entry))

    def populate(self, pdf_path):
        reader = PdfReader(pdf_path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

        # Find Bibliography
        m = re.search(r"(R\s*e\s*f\s*e\s*r\s*e\s*n\s*c\s*e\s*s|R\s*E\s*F\s*E\s*R\s*E\s*N\s*C\s*E\s*S|B\s*i\s*b\s*l\s*i\s*o\s*g\s*r\s*a\s*p\s*h\s*y|B\s*I\s*B\s*L\s*I\s*O\s*G\s*R\s*A\s*P\s*H\s*Y)", text)
        start = m.end()

        # If appendix, bibliography ends before it
        m2 = re.search(r"\bAppendix\b", text[start:], re.IGNORECASE)
        if m2:
            end = start + m2.start()
            self.bib_text = text[start:end]
        else:
            self.bib_text = text[start:]

        # Parse bibliography into list of entries
        if self.bib_format == "ieee":
            self.parse_ieee()
        else:
            self.parse_acm()
    

    def validate(self):
        #entry = self.entries[7]
        #entry.validate()
        for entry in self.entries:
            entry.validate()
            entry.write_not_found()


    def print_matches_to_csv(self, filename):
        csvfile = open("%s.csv"%filename, "w", newline="", encoding="utf-8")
        writer = csv.writer(csvfile)
        writer.writerow(["Citation No.", 
                         "Match Likelihood", 
                         "ID (Arxiv/DOI) Match",
                         "URL Exists",
                         "Input URL",
                         "Input Title",
                         "Best Match Title",
                         "Input Authors",
                         "Best Match Authors",
                         "Best Match URL",
                         "Full Input Citation"])
        
        for entry in self.entries:
            entry.write_to_csv(writer)
        csvfile.close()

    def print_matches_to_stdout(self):
        for entry in self.entries:
            entry.write_to_stdout()


#################################################
#### Methods for Cleaning BibItems           ####
#################################################
def normalize_text(s):
    s0 = s.replace('-\n', '')
    s0 = s0.replace('\n', ' ')
    s0 = re.sub(r'[^A-Za-z0-9 ]+', ' ', s0)
    s0 = s0.replace('  ', ' ');
    return s0.lower().strip() 

def normalize_hyphen_text(s):
    s1 = s.replace('-\n', '-')
    s1 = s1.replace('\n', ' ')
    s1 = re.sub(r'[^A-Za-z0-9 ]+', ' ', s1)
    s1 = s1.replace('  ', ' ');
    return s1.lower().strip()

# ---------------------------
# Main Logic
# ---------------------------
def first_author(input_authors, found_authors):
    if not input_authors or not found_authors:
        return False

    # Take first input author (last name only, lowercase)
    first_input = input_authors[0].lower()

    for f in found_authors:
        f = f.lower()
        if len(f) <= 1:
            continue
        if first_input in f or f in first_input:
            return True  # first author found

    return False

def authors_overlap(input_authors, found_authors):
    norm_in = [a.lower() for a in (input_authors or [])]
    norm_found = [a.lower() for a in (found_authors or [])]

    hits = 0
    if not first_author(input_authors, found_authors):
        return hits
    for a in norm_in:
        if len(a) <= 1:
            continue
        for f in norm_found:
            if (len(f) <= 1):
                continue
            if a in f or f in a:  # substring match
                hits += 1
                break
    return hits


# ---------------------------
# CLI
# ---------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parse_bib.py <pdf_path> <(optional)ieee|acm>")
        sys.exit(1)
    pdf_path = sys.argv[1]
    style = 'ieee'
    if len(sys.argv) > 2:
        style = sys.argv[2]

    # if passed filename, will output to csv
    filename = None
    if len(sys.argv) > 3:
        filename = sys.argv[3]

    bib = Bibliography(style)
    bib.populate(pdf_path)
    bib.validate()
    if filename:
        bib.print_matches_to_csv(filename)

