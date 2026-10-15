from dataclasses import dataclass


@dataclass
class SearchResult:
    content: str
    source: str
    source_type: str
    authority_score: float
    freshness_score: float
    relevance_score: float
    knowledge_entry_id: str
    title: str = ""
    publish_year: int = 0
    url: str = ""
