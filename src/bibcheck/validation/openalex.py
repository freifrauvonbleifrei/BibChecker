__all__ = ["parse_openalex", "search_no_title", "search_openalex"]

def parse_openalex(citation, validation, results):
    if results is None:
        return

    results = results.json().get("results", [])
    for item in results:
        title = item.get("title", "")
        authors = []
        for author in item.get("authorships", []):
            name = author.get("author", {}).get("display_name")
            if name:
                authors.append(name)
        validation.compare(citation, title, authors)
        if validation.score_title == 1.0 and validation.authors:
            return

def search_no_title(citation, validation):
    url = f"https://api.openalex.org/works"
    params = {
            "search": citation.entry,
            "per-page": 5
            }
    parse_openalex(citation, validation, validation.search_request(url, params))

def search_openalex(citation, validation):
    url = f"https://api.openalex.org/works"
    params = {
            "search": citation.norm_title,
            "per-page": 5
            }
    parse_openalex(citation, validation, validation.search_request(url, params))
    if validation.score_title == 1.0 and validation.authors:
        return

    if citation.norm_concat_title:
        params = {
                "search": citation.norm_concat_title,
                "per-page": 5
                }
        parse_openalex(citation, validation, validation.search_request(url, params))
        if validation.score_title == 1.0 and validation.authors:
            return

    if ":" in citation.title:
        title = citation.title.split(":")[0]
        params = {
            "search": title,
            "per-page": 5
            }
        parse_openalex(citation, validation, validation.search_request(url, params))
        if validation.score_title == 1.0 and validation.authors:
            return

