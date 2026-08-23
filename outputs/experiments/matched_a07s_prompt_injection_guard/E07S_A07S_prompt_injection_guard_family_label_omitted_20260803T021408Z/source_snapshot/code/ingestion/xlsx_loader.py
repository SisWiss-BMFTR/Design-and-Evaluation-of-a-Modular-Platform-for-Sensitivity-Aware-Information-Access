import pandas as pd
from pathlib import Path
from typing import List

def load_xlsx_as_text(data_path: Path) -> List[str]:
    excel = pd.read_excel(data_path, sheet_name=None)
    rows_as_text = []

    for sheet_name, df in excel.items():
        for _, row in df.iterrows():
            row_text = f"Sheet: {sheet_name}\n"
            row_text += "\n".join(
                [f"{col}: {row[col]}" for col in df.columns]
            )
            rows_as_text.append(row_text)

    return rows_as_text
