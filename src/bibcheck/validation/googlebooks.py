__all__ = ["parse_googlebooks", "search_googlebooks"]

def parse_googlebooks(citation, validation, results):
    if results is None:
        return

    for item in results.json().get("items", []):
        info = item.get("volumeInfo", {})
        title = info.get("title") or ""
        authors = [author for author in info.get("authors", [])]
        validation.compare(citation, title, authors)
        if validation.score_title == 1 and validation.authors:
            return

def search_googlebooks(citation, validation):
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {
        "q": citation.norm_title,
        "maxResults": 5,
        "printType": "books",
        "orderBy": "relevance"
    }
    parse_googlebooks(citation, validation, validation.search_request(url, params))
    if validation.score_title == 1.0 and validation.authors:
        return

    if citation.norm_concat_title:
        params = {
            "q": citation.norm_concat_title,
            "maxResults": 5,
            "printType": "books",
            "orderBy": "relevance"
        }
        parse_googlebooks(citation, validation, validation.search_request(url, params))




