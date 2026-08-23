from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BaseGenerator(ABC):
    @abstractmethod
    def generate(
        self,
        query: str,
        context_chunks: List[str],
        conversation_messages: Optional[List[Dict[str, str]]] = None,
        memory_summary: str = "",
        memory_snippets: Optional[List[str]] = None,
    ) -> str:
        pass

    @abstractmethod
    def summarize_conversation(
        self,
        existing_summary: str,
        turns: List[Dict[str, str]],
    ) -> str:
        pass
