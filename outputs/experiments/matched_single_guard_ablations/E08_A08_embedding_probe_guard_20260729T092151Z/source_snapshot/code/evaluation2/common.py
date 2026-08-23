from security.field_access import SECURE_RAG_MODE, SENSITIVITY_EVAL_MODE


RAG_MODE_CHOICES = [SECURE_RAG_MODE, SENSITIVITY_EVAL_MODE]


def add_rag_mode_argument(parser) -> None:
    parser.add_argument(
        "--rag-mode",
        choices=RAG_MODE_CHOICES,
        required=True,
        help="Required RAG mode for this final thesis run.",
    )
