__all__ = ["parse_semantic_scholar", "search_semantic_scholar"]

def parse_semantic_scholar(citation, validation, results):
    if results is None:
        return

    data = results.json().get("data", [])
    for item in data:
        title = item.get("title", "")
        authors = item.get("authors", [])
        validation.compare(citation, title, authors)
        if validation.score_title == 1.0 and validation.authors:
            return

def search_semantic_scholar(citation, validation):
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
            "query": citation.norm_title,
            "limit": 5,
            "fields": "title,authors,year,venue,externalIds"
        }
    parse_semantic_scholar(citation, validation, validation.search_request(url, params))
    if validation.score_title == 1.0 and validation.authors:
        return

    if citation.norm_concat_title:
        params = {
                "query": citation.norm_title,
                "limit": 5,
                "fields": "title,authors,year,venue,externalIds"
            }
        parse_semantic_scholar(citation, validation, validation.search_request(url, params))


