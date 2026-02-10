__all__ = ["parse_datacite", "search_datacite_doi"]

def parse_datacite(citation, validation, results):
    if results is None:
        return

    data = results.json().get("data", {}).get("attributes", {})
    title = data.get("titles", [{}])[0].get("title", "")
    creators = data.get("creators", [])
    authors = []
    for c in creators:
        name = c.get("familyName") or c.get("name") or ""
        if name:
            authors.append(name)
    validation.compare(citation, title, authors)

def search_datacite_doi(citation, validation):
    url = f"https://api.datacite.org/dois/{citation.doi}"
    parse_datacite(citation, validation, validation.search_request(url))
    if validation.score_title == 1.0 and validation.authors:
        return

    if citation.doi2:
        url = f"https://api.datacite.org/dois/{citation.doi2}"
        parse_datacite(citation, validation, validation.search_request(url))

