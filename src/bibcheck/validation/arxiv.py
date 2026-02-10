__all__ = ["parse_arxiv", "search_arxiv_id", "search_arxiv"]

import feedparser

def parse_arxiv(citation, validation, results):
    if results is None:
        return

    feed = feedparser.parse(results.text)
    entries = getattr(feed, "entries", [])
    for i, entry in enumerate(entries[:5], start=1):
        title = (entry.get("title", "") or "").strip().replace("\n", " ")
        authors = []
        for a in entry.get("authors", []):
            name = getattr(a, "name", None)
            if name:
                authors.append(name)

        validation.compare(citation, title, authors)
        if validation.score_title == 1 and validation.authors:
            return    

def search_arxiv_id(citation, validation):
    url = f"http://export.arxiv.org/api/query?id_list={citation.arxiv_id}"
    parse_arxiv(citation, validation, validation.search_request(url))


def search_arxiv(citation, validation):
    url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f'ti:"{citation.norm_title}"',
        "max_results": 5
    }
    parse_arxiv(citation, validation, validation.search_request(url, params))
    if validation.score_title == 1.0 and validation.authors:
        return
    
    if citation.norm_concat_title:
        params = {
            "search_query": f'ti:"{citation.norm_concat_title}"',
            "max_results": 5
        }
        parse_arxiv(citation, validation, validation.search_request(url, params))

