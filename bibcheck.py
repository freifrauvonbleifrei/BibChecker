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



cr = Crossref(timeout=30)

class Citation:
    number = ""
    entry = ""

    title = ""
    venue = ""
    authors = ""
    doi = ""
    url = ""

    match_title = ""
    match_venue = ""
    match_url = ""
    match_authors = ""
    match_percent = ""

    def __init__(self, number, entry):
        self.match = False
        self.match_percent = 0

        self.number = number
        self.entry = entry

        self.title = None
        self.authors = None
        self.venue = None
        self.url = None
        self.doi = None
        self.url_exists = None
        self.id_match = None

        author_block = None
        self.arxiv_id = None

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

        # Split into title, author, venue
        m = re.search(
            r"^(.*?)['“\"](.+?)['”\"](?:\s*,?\s*(.+?))?(?:[.,]?\s*\d{4}.*)?$",
            entry,
            re.DOTALL
        )
        if m:
            author_block = m.group(1).strip(" ,")
            self.title = m.group(2).strip()
            self.venue = m.group(3).strip(" .,;")        
        else:
            # Book / fallback
            # Split off the year at the end
            parts = re.split(r",?\s*(\d{4})[.,]?\s*$", entry)
            if len(parts) >= 2:
                pre_year = parts[0]   
                if "," in pre_year:
                    author_block, title_part = pre_year.split(",", 1)
                    self.title = re.split(r"\.\s*", title_part, maxsplit=1)[0].strip()

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
        self.norm_hyphen_title = None
        self.title_tokens = None
        self.title_no_numbers = None
        self.search_title = None

        if self.title:
            self.norm_title = normalize_text(self.title)
            self.norm_hyphen_title = remove_newlines(self.norm_title)
            self.norm_title = remove_hyphens(self.norm_title)

            self.title_tokens = create_tokens(self.norm_title) 
            self.title_hyphen_tokens = create_tokens(self.norm_hyphen_title)
            self.title_no_numbers = strip_numbers(self.norm_title)
            self.search_title = quote_plus(f"ti:{self.title_no_numbers.replace("-", " ")}")

        if "github.com" in self.entry.lower():
            self.match_percent = 0.99
            self.match_title = "GitHub Repository"
        elif "docs.amd.com" in self.entry.lower():
            self.match_percent = 0.99
            self.match_title = "AMD Docs"
        elif "developer.nvidia.com" in self.entry.lower():
            self.match_percent = 0.99
            self.match_title = "NVIDIA Docs"
        elif ".pdf" in self.entry.lower():
            self.match_percent = 0.99
            self.match_title = "Included .pdf Link"



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

        self.search_openalex()
        if self.match_percent == 1.0:
            return

        self.search_googlebooks()
        if self.match_percent == 1.0:
            return

        self.search_arxiv()
        if self.match_percent == 1.0:
            return

        self.search_crossref()
        if self.match_percent == 1.0:
            return


    def compare(self, title, authors, venue, url):
        if not title:
            return

        norm_found_title = normalize_text(title)
        found_tokens = create_tokens(norm_found_title)
        overlap = len(self.title_tokens & found_tokens)
        match_percent = (1.0 * overlap) / max(len(self.title_tokens), len(found_tokens))
        max_match = match_percent

        if (match_percent > self.match_percent and authors_overlap(self.authors, authors)):
            self.match_percent = match_percent
            self.match_title = title
            self.match_authors = authors
            self.match_venue = venue
            self.match_url = url

        overlap = len(self.title_hyphen_tokens & found_tokens)
        match_percent = (1.0 * overlap) / max(len(self.title_hyphen_tokens), len(found_tokens))
        if match_percent > max_match:
            max_match = match_percent

        if (match_percent > self.match_percent and authors_overlap(self.authors, authors)):
            self.match_percent = match_percent
            self.match_title = title
            self.match_authors = authors
            self.match_venue = venue
            self.match_url = url

        return max_match

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
        
    def search_crossref(self):
        try:
            result = cr.works(query_title = self.title_no_numbers, limit = 30)
            items = result.get("message", {}).get("items", [])
            for item in items:
                title = item.get("title", [""])[0]
                authors = [a.get("family", "").lower() for a in item.get("author", [])]
                venue = ""
                if item.get("container-title"):
                    venue = item.get("container-title", [""])[0]
                self.compare(title, authors, venue, None)
        except Timeout:
            print("Crossref timeout, retrying")
            sleep(2)
            self.search_crossref()
        except RuntimeError as e:
            if "timed out" in str(e).lower():
                print("Crossref timeout, retrying")
                sleep(2)
                self.check_doi()
            else:
                raise


    def search_openalex(self):    
        url = f"https://api.openalex.org/works?filter=title.search:{self.search_title}"
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                data = r.json()
                for item in data.get("results", []):
                    title = item.get("title", "")
                    authors = [a["author"]["display_name"] for a in item.get("authorships", [])]
                    venue = item.get("host_venue", {}).get("display_name")
                    self.compare(title, authors, venue, url)
        except requests.exceptions.Timeout:
            print("OpenAlex timeout on url, retrying", url)
            sleep(2)
            self.search_openalex()

    def search_arxiv(self):
        url = f"http://export.arxiv.org/api/query?search_query={self.search_title}&max_results=10"
        try:
            feed = feedparser.parse(url)

            for entry in feed.entries:
                title = entry.get("title", "")
                authors = [a.name for a in entry.get("authors", [])]
                self.compare(title, authors, "arXiv", url)
        except Timeout:
            print("ArXiv timeout on url, retrying", url)
            sleep(2)
            self.search_arxiv()

    def search_googlebooks(self):
        url = f"https://www.googleapis.com/books/v1/volumes?q={self.search_title}"
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
            self.search_googlebooks()


    def write_to_csv(self, writer):
        writer.writerow([self.number, self.match_percent, self.id_match, self.url_exists, self.url, self.title, self.match_title, self.authors, self.match_authors, self.match_url, self.entry])

    def write_to_stdout(self):
        if self.match_percent >= 0.99:
            color = "\033[92m"   # green
        else:
            color = "\033[91m"   # red

        print(color + self.number, self.entry, "Closest Match: ", self.match_title, self.match_authors)
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
            self.entries.append(Citation(i, entry))

    def parse_ieee(self):
        pattern = r"\[(\d+)\]\s*(.+?)(?=\[\d+\]|\Z)"
        entries = re.findall(pattern, self.bib_text, re.DOTALL)
        for i, entry in entries:
            clean = " ".join(entry.split()).strip()
            self.entries.append(Citation(i, entry))

    def populate(self, pdf_path):
        reader = PdfReader(pdf_path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

        # Find Bibliography
        m = re.search(r"(r\s*e\s*f\s*e\s*r\s*e\s*n\s*c\s*e\s*s|b\s*i\s*b\s*l\s*i\s*o\s*g\s*r\s*a\s*p\s*h\s*y)", text, re.IGNORECASE)
        start = m.start()

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
        for entry in self.entries:
            entry.validate()
            entry.write_to_stdout()
        #self.entries[32].validate()


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
def strip_numbers(text):
    # Remove commas from large numbers
    text = re.sub(r'(?<=\d),(?=\d)', '', text)    
    # Remove all numbers
    return re.sub(r" \d+ ", " ", text).strip()

def normalize_text(s):
    if not s:
        return None

    s = s.strip(" .,;:")
    s = html.unescape(s)
    s = re.sub(r"<[^>]+>", "", s) 
    s = unicodedata.normalize("NFC", s)    
    s = re.sub(r"\s+([́̀̈^~])", r"\1", s)  # handles ´, `, ¨, ^, ~
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[‐-‒–—−]", "-", s)
    return s.lower().strip()

def remove_hyphens(s):
    s = s.replace("\n", " ")
    s = re.sub(r"-\s+", "", s)
    s = re.sub(r"\s+", " ", s)
    return s

def remove_newlines(s):
    s = s.replace("\n", " ")
    s = re.sub(r"-\s+", "-", s)
    return s

def create_tokens(text):
    if not text:
        return

    tokens = list()
    for word in text.split():
        if any(ord(ch) > 127 for ch in word):
            continue
        clean = re.sub(r"[^a-z0-9]", "", word.lower())
        if clean:
            tokens.append(clean)
    return set(tokens)

# ---------------------------
# Main Logic
# ---------------------------
def authors_overlap(input_authors, found_authors):
    norm_in = [a.lower() for a in (input_authors or [])]
    norm_found = [a.lower() for a in (found_authors or [])]

    hits = 0
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

