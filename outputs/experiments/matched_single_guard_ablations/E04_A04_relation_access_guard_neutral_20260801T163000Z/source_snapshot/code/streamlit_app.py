from datetime import datetime

import streamlit as st

from config.env_loader import load_env_file
from rag_setup import build_shared_components, create_rag_pipeline
from security.field_access import (
    SECURE_RAG_MODE,
    SENSITIVITY_EVAL_MODE,
    allowed_labels_for_role,
    default_user_role,
    load_sensitivity_policy,
    policy_role_names,
    sensitivity_rank,
)

load_env_file()

st.set_page_config(page_title="RAG Chat", page_icon=":speech_balloon:", layout="wide")


ACCESS_POLICY = load_sensitivity_policy()
ACCESS_LEVELS = {
    role: allowed_labels_for_role(role, ACCESS_POLICY)
    for role in policy_role_names(ACCESS_POLICY)
}

ACCESS_RANKS = {
    role: max((sensitivity_rank(label, ACCESS_POLICY) for label in labels), default=0)
    for role, labels in ACCESS_LEVELS.items()
}

DEFAULT_ACCESS_LEVEL = default_user_role(ACCESS_POLICY)

RAG_MODES = (SENSITIVITY_EVAL_MODE, SECURE_RAG_MODE)
DEFAULT_RAG_MODE = SENSITIVITY_EVAL_MODE
RAG_MODE_HELP = {
    SECURE_RAG_MODE: "Filters fields before prompt construction.",
    SENSITIVITY_EVAL_MODE: "Sends mixed labeled context for leakage experiments.",
}


@st.cache_resource(show_spinner="Loading data and building retrieval index...")
def load_shared() -> dict:
    return build_shared_components(
        use_xlsx=True,
        use_multilevel=True,
    )


def new_chat_title(index: int) -> str:
    return f"Chat {index}"


def set_pipeline_config(pipeline, access_level: str, rag_mode: str) -> None:
    if hasattr(pipeline, "set_access_context"):
        pipeline.set_access_context(
            user_role=access_level,
            allowed_sensitivities=ACCESS_LEVELS[access_level],
        )
    else:
        pipeline.allowed_sensitivities = ACCESS_LEVELS[access_level]
        pipeline.user_role = access_level
    pipeline.rag_mode = rag_mode


def create_pipeline_for_chat(shared: dict, access_level: str, rag_mode: str):
    pipeline = create_rag_pipeline(
        shared,
        user_role=access_level,
        rag_mode=rag_mode,
    )
    set_pipeline_config(pipeline, access_level, rag_mode)
    return pipeline


def create_chat_session(chat_id: str, title: str, shared: dict) -> None:
    pipeline = create_pipeline_for_chat(shared, DEFAULT_ACCESS_LEVEL, DEFAULT_RAG_MODE)

    st.session_state.chat_sessions[chat_id] = {
        "title": title,
        "messages": [],
        "pipeline": pipeline,
        "access_level": DEFAULT_ACCESS_LEVEL,
        "rag_mode": DEFAULT_RAG_MODE,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    st.session_state.chat_order.append(chat_id)


def ensure_state(shared: dict) -> None:
    if "chat_sessions" not in st.session_state:
        st.session_state.chat_sessions = {}
    if "chat_order" not in st.session_state:
        st.session_state.chat_order = []
    if "active_chat_id" not in st.session_state:
        st.session_state.active_chat_id = None

    if not st.session_state.chat_order:
        first_chat_id = "chat-1"
        create_chat_session(first_chat_id, new_chat_title(1), shared)
        st.session_state.active_chat_id = first_chat_id


shared = load_shared()
ensure_state(shared)

st.title("RAG Chatbot")
st.caption(f"Indexed chunks: {shared['chunks_count']}")

with st.sidebar:
    st.header("Conversations")

    if st.button("+ New Chat", use_container_width=True):
        next_index = len(st.session_state.chat_order) + 1
        chat_id = f"chat-{next_index}"
        create_chat_session(chat_id, new_chat_title(next_index), shared)
        st.session_state.active_chat_id = chat_id
        st.rerun()

    chat_ids = st.session_state.chat_order
    selected_chat_id = st.radio(
        "Select chat",
        options=chat_ids,
        format_func=lambda cid: st.session_state.chat_sessions[cid]["title"],
        index=chat_ids.index(st.session_state.active_chat_id),
        key="chat_selector",
    )
    st.session_state.active_chat_id = selected_chat_id

    active_chat = st.session_state.chat_sessions[selected_chat_id]

    st.divider()
    st.header("RAG Mode")

    current_mode = active_chat.get("rag_mode", DEFAULT_RAG_MODE)
    if current_mode not in RAG_MODES:
        current_mode = DEFAULT_RAG_MODE
        active_chat["rag_mode"] = current_mode

    selected_mode = st.selectbox(
        "Mode",
        options=list(RAG_MODES),
        index=list(RAG_MODES).index(current_mode),
        help="Switch between normal enforcement and controlled sensitivity experiments.",
    )
    st.caption(RAG_MODE_HELP[selected_mode])

    st.divider()
    st.header("Access Control")

    current_access = active_chat.get("access_level", DEFAULT_ACCESS_LEVEL)
    if current_access not in ACCESS_LEVELS:
        current_access = DEFAULT_ACCESS_LEVEL
        active_chat["access_level"] = current_access
        set_pipeline_config(active_chat["pipeline"], current_access, current_mode)

    selected_access = st.selectbox(
        "Sensitivity level",
        options=list(ACCESS_LEVELS.keys()),
        index=list(ACCESS_LEVELS.keys()).index(current_access),
        help="Controls which fields are visible to this chat before prompt construction.",
    )

    mode_changed = selected_mode != current_mode
    access_changed = selected_access != current_access
    access_downgrade = (
        access_changed
        and ACCESS_RANKS[selected_access] < ACCESS_RANKS[current_access]
    )
    eval_access_changed = selected_mode == SENSITIVITY_EVAL_MODE and access_changed
    should_clear_chat = mode_changed or access_downgrade or eval_access_changed

    if mode_changed or access_changed:
        active_chat["rag_mode"] = selected_mode
        active_chat["access_level"] = selected_access

        if should_clear_chat:
            active_chat["messages"] = []
            active_chat["pipeline"] = create_pipeline_for_chat(
                shared,
                selected_access,
                selected_mode,
            )
            if mode_changed:
                st.warning("RAG mode changed, so this chat was cleared to keep experiment context separate.")
            elif eval_access_changed:
                st.warning("Experiment access changed, so this chat was cleared for a clean condition.")
            else:
                st.warning("Access level was lowered, so this chat was cleared to avoid memory leakage.")
        else:
            set_pipeline_config(active_chat["pipeline"], selected_access, selected_mode)

        st.rerun()
    else:
        set_pipeline_config(active_chat["pipeline"], selected_access, selected_mode)

    st.caption("Visible sensitivities: " + ", ".join(ACCESS_LEVELS[selected_access]))

    if selected_mode == SENSITIVITY_EVAL_MODE:
        st.caption("Experiment mode: mixed context is intentionally shown to the LLM with labels.")

active_chat = st.session_state.chat_sessions[st.session_state.active_chat_id]

for message in active_chat["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Ask a question about your data...")

if prompt:
    active_chat["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            answer = active_chat["pipeline"].query(prompt)
        st.markdown(answer)

    active_chat["messages"].append({"role": "assistant", "content": answer})

    if active_chat["title"].startswith("Chat ") and len(active_chat["messages"]) <= 2:
        active_chat["title"] = prompt.strip()[:40] or active_chat["title"]

    st.rerun()
