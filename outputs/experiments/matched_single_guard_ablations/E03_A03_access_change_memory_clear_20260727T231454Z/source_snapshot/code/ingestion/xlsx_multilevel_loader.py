import pandas as pd
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import defaultdict

from security.field_access import (
    load_sensitivity_policy,
    make_structured_field,
    max_sensitivity,
    normalize_sensitivity,
    sensitivity_rank,
)


def load_xlsx_multilevel(
    data_path: Path,
    policy_path: Optional[Path] = None,
    overrides_path: Optional[Path] = None,
) -> List[Dict]:
    """
    Loads multi-sheet Excel file and converts relational data
    into hierarchical RAG-ready documents with field-level
    sensitivity metadata.
    """
    sensitivity_policy = load_sensitivity_policy(policy_path=policy_path, overrides_path=overrides_path)

    def excel_row_index(index: Any) -> int:
        # Excel row numbers are 1-based and include the header row.
        try:
            return int(index) + 2
        except Exception:
            return 0

    def source(sheet_name: str, row_index: Any, document_id: str, column_name: str) -> Dict[str, Any]:
        return {
            "sheet_name": sheet_name,
            "row_index": excel_row_index(row_index),
            "document_id": document_id,
            "column_name": column_name,
        }

    def add_field(
        fields: List[Dict],
        field_name: str,
        value: Any,
        sheet_name: str,
        row_index: Any,
        document_id: str,
        column_name: str,
        sensitivity: str = None,
        category: str = None,
        display_name: str = None,
    ) -> None:
        field = make_structured_field(
            field_name=field_name,
            value=value,
            source=source(sheet_name, row_index, document_id, column_name),
            policy=sensitivity_policy,
            sensitivity=sensitivity,
            category=category,
            display_name=display_name,
        )
        if field:
            fields.append(field)

    def entity_metadata(
        entity_id: str,
        doc_type: str,
        fields: List[Dict],
        retrieval_sensitivity: Optional[str] = None,
        membership_sensitivity: Optional[str] = None,
    ) -> Dict:
        field_sensitivities = sorted(
            {str(field.get("sensitivity", "internal")) for field in fields},
            key=lambda label: sensitivity_rank(label, sensitivity_policy),
        )
        highest = max_sensitivity(fields, sensitivity_policy) if fields else sensitivity_policy["default_sensitivity"]
        return {
            "entity_id": entity_id,
            "sensitivity": "mixed" if len(field_sensitivities) > 1 else highest,
            "max_sensitivity": highest,
            "retrieval_sensitivity": normalize_sensitivity(
                retrieval_sensitivity or highest,
                sensitivity_policy,
            ),
            "membership_sensitivity": normalize_sensitivity(
                membership_sensitivity or retrieval_sensitivity or highest,
                sensitivity_policy,
            ),
            "field_sensitivities": field_sensitivities,
            "entity_fields": fields,
            "entity": {
                "entity_id": entity_id,
                "doc_type": doc_type,
                "fields": fields,
            },
        }

    # ==========================================================
    # Load Excel (all sheets)
    # ==========================================================
    excel = pd.read_excel(data_path, sheet_name=None)

    rezepturen_df = excel["Rezepturen"]
    verfahren_df = excel["Verfahren"]
    rezepte_df = excel["Rezepte"]
    eigenschaften_df = excel["Eigenschaften"]

    # Clean column names
    for df in [rezepturen_df, verfahren_df, rezepte_df, eigenschaften_df]:
        df.columns = df.columns.str.strip()

    documents: List[Dict] = []

    # ==========================================================
    # 1️⃣ FORMULATION DOCUMENTS
    # ==========================================================
    for rezeptur_id, group in rezepturen_df.groupby("Rezeptur-ID"):

        name = group["Name der Rezeptur"].iloc[0]
        category = group["Produktkategorie"].iloc[0]
        description = group["Beschreibung"].iloc[0]
        entity_id = f"formulation:{rezeptur_id}"
        first_index = group.index[0]
        fields: List[Dict] = []

        add_field(fields, "linked_rezeptur", rezeptur_id, "Rezepturen", first_index, entity_id, "Rezeptur-ID", display_name="rezeptur_id")
        add_field(fields, "formulation_name", name, "Rezepturen", first_index, entity_id, "Name der Rezeptur")
        add_field(fields, "formulation_category", category, "Rezepturen", first_index, entity_id, "Produktkategorie")
        add_field(fields, "formulation_description", description, "Rezepturen", first_index, entity_id, "Beschreibung")

        # Phase → list of ingredient lines
        phase_dict = defaultdict(list)

        for row_index, row in group.iterrows():
            phase = row.get("Phase", "Unknown")
            rohstoff = row.get("Rohstoff", "")
            inci = row.get("INCI", "")
            lieferant = row.get("Lieferant", "")
            menge = row.get("Menge (%)", "")
            claim = row.get("Claim", "")
            bemerkung = row.get("Bemerkung", "")

            if pd.notna(menge):
                try:
                    menge = f"{float(menge):.2f}"
                except Exception:
                    menge = str(menge)
            else:
                menge = "N/A"

            ingredient_line = f"- {rohstoff} (INCI: {inci})"

            phase_dict[phase].append(ingredient_line)

            add_field(fields, "formulation_phase", phase, "Rezepturen", row_index, entity_id, "Phase")
            add_field(fields, "ingredient", rohstoff, "Rezepturen", row_index, entity_id, "Rohstoff")
            add_field(fields, "inci", inci, "Rezepturen", row_index, entity_id, "INCI")
            add_field(fields, "supplier", lieferant, "Rezepturen", row_index, entity_id, "Lieferant")
            add_field(fields, "formulation_percentage", menge, "Rezepturen", row_index, entity_id, "Menge (%)")
            add_field(fields, "claim", claim, "Rezepturen", row_index, entity_id, "Claim")
            add_field(fields, "notes", bemerkung, "Rezepturen", row_index, entity_id, "Bemerkung")

        # Build hierarchical ingredient section
        ingredient_sections = []

        for phase in sorted(phase_dict.keys()):
            ingredient_sections.append(f"Phase {phase}:")
            ingredient_sections.extend(phase_dict[phase])
            ingredient_sections.append("")

        ingredients_text = "\n".join(ingredient_sections).strip()

        claims = [str(c).strip() for c in group["Claim"].dropna().unique()]
        claim_text = "\n".join([f"- {c}" for c in claims]) if len(claims) > 0 else "None"
        ingredient_names = [
            str(v).strip() for v in group["Rohstoff"].dropna().tolist() if str(v).strip()
        ]
        inci_names = [
            str(v).strip() for v in group["INCI"].dropna().tolist() if str(v).strip()
        ]
        suppliers = [
            str(v).strip() for v in group["Lieferant"].dropna().tolist() if str(v).strip()
        ]
        phases = [str(v).strip() for v in group["Phase"].dropna().tolist() if str(v).strip()]

        text = (
            f"FORMULATION: {rezeptur_id}\n"
            f"Name: {name}\n"
            f"Category: {category}\n"
            f"Description: {description}\n\n"
            f"Ingredients:\n\n"
            f"{ingredients_text}\n\n"
            f"Claims:\n"
            f"{claim_text}"
        )

        documents.append({
            "text": text,
            "metadata": {
                "doc_type": "formulation",
                "rezeptur_id": str(rezeptur_id),
                "formulation_name": str(name),
                "category": str(category),
                "description": str(description),
                "claims": claims,
                "ingredient_names": ingredient_names,
                "inci_names": sorted(set(inci_names)),
                "suppliers": sorted(set(suppliers)),
                "phases": sorted(set(phases)),
                **entity_metadata(
                    entity_id,
                    "formulation",
                    fields,
                    retrieval_sensitivity="protected",
                    membership_sensitivity="protected",
                ),
            }
        })

    # ==========================================================
    # 2️⃣ PROCESS DOCUMENTS
    # ==========================================================
    for row_index, row in verfahren_df.iterrows():
        verfahren_id = str(row["Verfahren-ID"])
        entity_id = f"process:{verfahren_id}"
        fields: List[Dict] = []

        add_field(fields, "linked_verfahren", verfahren_id, "Verfahren", row_index, entity_id, "Verfahren-ID", display_name="verfahren_id")
        add_field(fields, "process_name", row["Name des Verfahrens"], "Verfahren", row_index, entity_id, "Name des Verfahrens")
        add_field(fields, "process_description", row["Beschreibung"], "Verfahren", row_index, entity_id, "Beschreibung")
        add_field(fields, "process_step", row.get("Schritt 1", ""), "Verfahren", row_index, entity_id, "Schritt 1", display_name="process_step_1")
        add_field(fields, "process_step", row.get("Schritt 2", ""), "Verfahren", row_index, entity_id, "Schritt 2", display_name="process_step_2")
        add_field(fields, "process_step", row.get("Schritt 3", ""), "Verfahren", row_index, entity_id, "Schritt 3", display_name="process_step_3")
        add_field(fields, "process_step", row.get("Schritt 4", ""), "Verfahren", row_index, entity_id, "Schritt 4", display_name="process_step_4")
        add_field(fields, "linked_rezeptur", row["Verwendete Rezeptur-ID"], "Verfahren", row_index, entity_id, "Verwendete Rezeptur-ID")
        add_field(fields, "notes", row.get("Bemerkung", ""), "Verfahren", row_index, entity_id, "Bemerkung")

        text = (
            f"PROCESS: {row['Verfahren-ID']}\n"
            f"Name: {row['Name des Verfahrens']}\n"
            f"Description: {row['Beschreibung']}\n\n"
            f"Steps:\n\n"
            f"1. {row['Schritt 1']}\n\n"
            f"2. {row['Schritt 2']}\n\n"
            f"3. {row['Schritt 3']}\n\n"
            f"4. {row['Schritt 4']}"
        )

        documents.append({
            "text": text,
            "metadata": {
                "doc_type": "process",
                "verfahren_id": str(row["Verfahren-ID"]),
                "rezeptur_id": str(row["Verwendete Rezeptur-ID"]),
                "process_name": str(row["Name des Verfahrens"]),
                "process_description": str(row["Beschreibung"]),
                "steps": [
                    str(row.get("Schritt 1", "")),
                    str(row.get("Schritt 2", "")),
                    str(row.get("Schritt 3", "")),
                    str(row.get("Schritt 4", "")),
                ],
                **entity_metadata(entity_id, "process", fields, retrieval_sensitivity="protected"),
            }
        })

    # ==========================================================
    # 3. PRODUCT DOCUMENTS
    # ==========================================================
    for row_index, row in rezepte_df.iterrows():

        rezept_id = row["Rezept-ID"]
        entity_id = f"product:{rezept_id}"
        fields: List[Dict] = []

        add_field(fields, "product_id", rezept_id, "Rezepte", row_index, entity_id, "Rezept-ID")
        add_field(fields, "product_name", row["Name des Produkts"], "Rezepte", row_index, entity_id, "Name des Produkts")
        add_field(fields, "target_market", row["Zielmarkt/Verwendung"], "Rezepte", row_index, entity_id, "Zielmarkt/Verwendung")
        add_field(fields, "linked_rezeptur", row["Zugehörige Rezeptur-ID"], "Rezepte", row_index, entity_id, "Zugehörige Rezeptur-ID")
        add_field(fields, "linked_verfahren", row["Zugehöriges Verfahren-ID"], "Rezepte", row_index, entity_id, "Zugehöriges Verfahren-ID")
        add_field(fields, "notes", row.get("Bemerkung", ""), "Rezepte", row_index, entity_id, "Bemerkung")

        # Relational filtering (manual join)
        eigenschaften = eigenschaften_df[
            eigenschaften_df["Rezept-ID"] == rezept_id
        ]

        prop_lines = []
        property_parameters = []
        property_values = []
        property_methods = []
        testers = []
        test_dates = []

        for prop_index, prop in eigenschaften.iterrows():
            parameter = prop.get("Parameter", "")
            wert = prop.get("Wert", "")
            methode = prop.get("Bedingung/Methode", "")
            pruefdatum = prop.get("Prüfdatum", "")
            pruefer = prop.get("Prüfer", "")

            # Collect structured fields for robust retrieval/filtering.
            if str(parameter).strip():
                property_parameters.append(str(parameter).strip())
            if str(wert).strip():
                property_values.append(str(wert).strip())
            if str(methode).strip():
                property_methods.append(str(methode).strip())
            if str(pruefer).strip():
                testers.append(str(pruefer).strip())
            if str(pruefdatum).strip():
                test_dates.append(str(pruefdatum).strip())

            prop_lines.append(
                f"- {parameter}: {wert} "
                f"(Method: {methode}, Date: {pruefdatum}, Tester: {pruefer})"
            )

            parameter_label = str(parameter).strip() or "property_value"
            add_field(fields, "property_parameter", parameter, "Eigenschaften", prop_index, entity_id, "Parameter", display_name="property_parameter")
            add_field(fields, "property_value", wert, "Eigenschaften", prop_index, entity_id, "Wert", display_name=parameter_label)
            add_field(fields, "test_method", methode, "Eigenschaften", prop_index, entity_id, "Bedingung/Methode")
            add_field(fields, "test_date", pruefdatum, "Eigenschaften", prop_index, entity_id, "Prüfdatum")
            add_field(fields, "tester", pruefer, "Eigenschaften", prop_index, entity_id, "Prüfer")

        prop_text = "\n".join(prop_lines) if prop_lines else "None"

        product_text = (
            "PRODUCT: " + str(rezept_id) + "\n"
            "Name: " + str(row["Name des Produkts"]) + "\n"
            "Target Market: " + str(row["Zielmarkt/Verwendung"])
        )
        documents.append({
            "text": product_text,
            "metadata": {
                "doc_type": "product",
                "rezept_id": str(rezept_id),
                "rezeptur_id": str(row["Zugehörige Rezeptur-ID"]),
                "verfahren_id": str(row["Zugehöriges Verfahren-ID"]),
                "product_name": str(row["Name des Produkts"]),
                "target_market": str(row["Zielmarkt/Verwendung"]),
                "property_parameters": sorted(set(property_parameters)),
                "property_values": sorted(set(property_values)),
                "property_methods": sorted(set(property_methods)),
                "testers": sorted(set(testers)),
                "test_dates": sorted(set(test_dates)),
                **entity_metadata(
                    entity_id,
                    "product",
                    fields,
                    retrieval_sensitivity="public",
                    membership_sensitivity="public",
                ),
            }
        })
    return documents
