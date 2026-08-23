from abc import ABC, abstractmethod
import numpy as np # pyright: ignore[reportMissingImports]
from typing import Dict, List

class BaseRetriever(ABC):
    @abstractmethod
    def retrieve(self, query_embedding: np.ndarray, top_k: int) -> List[Dict]:
        pass
