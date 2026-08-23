from pathlib import Path
from typing import List

def load_documents(data_dir: Path) -> List[str]:
    texts = []
    for file in data_dir.glob("*.txt"):
        texts.append(file.read_text(encoding="utf-8"))
    return texts
