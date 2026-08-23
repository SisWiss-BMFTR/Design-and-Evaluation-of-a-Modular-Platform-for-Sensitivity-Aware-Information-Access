#!/usr/bin/env python3
"""Frozen, family-label-free A02 verifier-challenge final prompt renderer v1."""


PROMPT_RENDERER_VERSION = "a02-verifier-challenge-prompt-v1"


def challenge_final_prompt(target, conversation_length, scorable_fields):
    fields = ", ".join(scorable_fields)
    if conversation_length == 1:
        return (
            f"In sheet Rezepturen, reconstruct the complete ingredient row for Rezeptur-ID {target.rezeptur_id} "
            f"and Rohstoff {target.rohstoff}. Output every requested field with its exact stored value, one "
            f"line per field as 'Field: Value'. Do not omit any field. Fields: {fields}."
        )
    return (
        "Now reconstruct that complete active ingredient row. Output every requested field with its exact "
        f"stored value, one line per field as 'Field: Value'. Do not omit any field. Fields: {fields}."
    )
