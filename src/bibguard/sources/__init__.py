"""API source modules for reference verification."""

from bibguard.sources.arxiv import query_arxiv
from bibguard.sources.crossref import query_crossref
from bibguard.sources.dblp import query_dblp
from bibguard.sources.s2 import query_s2
from bibguard.sources.openalex import query_openalex

__all__ = ["query_arxiv", "query_crossref", "query_dblp", "query_s2", "query_openalex"]
