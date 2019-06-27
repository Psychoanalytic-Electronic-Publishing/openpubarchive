
BASEURL = "127.0.0.1:8000"

IMAGES = "images"
HITMARKERSTART = "[[starthit]]"  # using non xml type so we can remove all tags but leave these!
HITMARKEREND = "[[endhit]]"

# parameter descriptions for documentation
DESCRIPTION_LIMIT = "Number of items to return"
DESCRIPTION_OFFSET = "Start return with this item, referencing the sequence number in the return set (for paging results)"
DESCRIPTION_PEPCODE = "The 2-8 character assigned PEP Code for source (e.g., APA, CPS, IJP, ANIJP-FR)"
DESCRIPTION_REQUEST = "The request object, passed in automatically by FastAPI"
DESCRIPTION_AUTHORNAMEORPARTIAL = "The author name or a partial name (no wildcard) for which to return data"
DESCRIPTION_DOCIDORPARTIAL = "The document ID (e.g., IJP.077.0217A) or a partial ID (e.g., IJP.077,  no wildcard) for which to return data"
DESCRIPTION_RETURNFORMATS = "The format of the returned document data.  One of: 'HTML', 'XML', 'TEXTONLY'"
DESCRIPTION_DOCDOWNLOADFORMAT = "The format of the downloaded document data.  One of: 'HTML', 'PDF', 'EPUB'"
DESCRIPTION_SOURCETYPE = "The class of source type for the metadata.  One of: 'Journals', 'Books', 'Videos'"