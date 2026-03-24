"""API source modules for reference verification."""

from ref_check.sources.arxiv import query_arxiv
from ref_check.sources.crossref import query_crossref
from ref_check.sources.dblp import query_dblp
from ref_check.sources.s2 import query_s2
from ref_check.sources.openalex import query_openalex

__all__ = ["query_arxiv", "query_crossref", "query_dblp", "query_s2", "query_openalex"]
