import base64
import io
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from etl_ai_pipeline.nodes import ETLAgent, validate_table_name

APP_DIR = Path(__file__).resolve().parents[1]
BOT_IMAGE = APP_DIR / "assert" / "AI bot.gif"
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
BOT_IMAGE_DATA = base64.b64encode(BOT_IMAGE.read_bytes()).decode("ascii")
for widget_key in ("upload_widget_key", "prompt_widget_key"):
    if widget_key not in st.session_state:
        st.session_state[widget_key] = uuid.uuid4().hex

QUICK = {
    "Drop missing rows": "Remove rows with missing values",
    "Remove duplicates": "Remove duplicate rows",
    "Row-wise mean": "Add a column with the mean of all numeric columns for each row",
    "Top 3 by total": "Show the top 3 categories by total of the main numeric column",
}

CHAT_STATE_KEYS = (
    "thread_id",
    "current_prompt",
    "answer",
    "info",
    "error",
    "completion",
    "completion_table_name",
    "table_name_input",
)

if "history" not in st.session_state:
    st.session_state.history = []
    
    
st.set_page_config(
    page_title="ETLix | AI ETL Builder",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_agent():
    return ETLAgent()


agent = get_agent()


def save_current_chat():
    thread_id = st.session_state.get("thread_id")
    prompt = st.session_state.get("current_prompt")
    if not thread_id or not prompt:
        return

    title = " ".join(prompt.split())
    if len(title) > 48:
        title = f"{title[:45].rstrip()}..."
    chat = {
        key: st.session_state[key]
        for key in CHAT_STATE_KEYS
        if key in st.session_state
    }
    chat["title"] = title

    history = st.session_state.history
    history[:] = [item for item in history if item["thread_id"] != thread_id]
    history.insert(0, chat)


def run_instruction(text, uploaded):
    if uploaded is None:
        st.warning("Please upload a CSV first.")
        return
    has_previous_run = any(
        st.session_state.get(key)
        for key in ("answer", "info", "error", "completion")
    )
    st.session_state.pop("completion", None)
    st.session_state.pop("completion_table_name", None)
    st.session_state.pop("table_name_input", None)
    file_path = UPLOAD_DIR / f"{uuid.uuid4().hex}.csv"
    file_path.write_bytes(uploaded.getvalue())
    thread_id = st.session_state.get("thread_id")
    if has_previous_run or not thread_id:
        thread_id = uuid.uuid4().hex
    
    past = st.session_state.history[-5:]
    history_text = "\n".join(
        f"- {chat.get('current_prompt') or chat.get('title', '')}" for chat in past
    ).strip() or "None"
    with st.spinner("ETLix is writing and testing the code..."):     
        result = agent.start(str(file_path), text, thread_id ,history_text)
    spec = result.get("spec") or {}
    st.session_state.answer = None
    if spec.get("kind") == "analyze" and not result.get("error"):
        st.session_state.answer = {
            "explanation": spec["explanation"],
            "code": spec["code"],
            "rows": result["preview"],
        }
    st.session_state.thread_id = thread_id
    st.session_state.current_prompt = text
    st.session_state.info = (
        result["__interrupt__"][0].value if "__interrupt__" in result else None
    )
    st.session_state.error = result.get("error")
    save_current_chat()


def start_new_chat():
    save_current_chat()
    prompt_widget_key = st.session_state.get("prompt_widget_key")
    if prompt_widget_key:
        st.session_state[f"custom_prompt_{prompt_widget_key}"] = ""
    for key in (
        "thread_id",
        "current_prompt",
        "answer",
        "info",
        "error",
        "completion",
        "completion_table_name",
        "table_name_input",
    ):
        st.session_state.pop(key, None)
    st.session_state.thread_id = uuid.uuid4().hex
    st.session_state.upload_widget_key = uuid.uuid4().hex
    st.session_state.prompt_widget_key = uuid.uuid4().hex


def open_chat(thread_id):
    chat = next(
        item for item in st.session_state.history if item["thread_id"] == thread_id
    )
    prompt_widget_key = st.session_state.get("prompt_widget_key")
    if prompt_widget_key:
        st.session_state[f"custom_prompt_{prompt_widget_key}"] = ""
    for key in CHAT_STATE_KEYS:
        if key in chat:
            st.session_state[key] = chat[key]
        else:
            st.session_state.pop(key, None)
    st.session_state.upload_widget_key = uuid.uuid4().hex
    st.session_state.prompt_widget_key = uuid.uuid4().hex


def clear_chat_history():
    st.session_state.history.clear()


st.markdown(
    f"<style>\n{Path(__file__).with_name('style.css').read_text(encoding='utf-8')}\n</style>",
    unsafe_allow_html=True,
)



with st.sidebar:
    st.markdown(
        f'<div class="brand"><img src="data:image/gif;base64,{BOT_IMAGE_DATA}" '
        'alt=""><h1 class= "heading">ETLix</h1></div>',
        unsafe_allow_html=True,
    )
    st.button(
        "＋  New chat",
        width='stretch',
        type="primary",
        on_click=start_new_chat,
    )

    st.markdown('<div class="section-label">Previous chats</div>', unsafe_allow_html=True)
    if st.session_state.history:
        st.button(
            "Clear previous chats",
            key="clear-chat-history",
            width="stretch",
            on_click=clear_chat_history,
        )
        for chat in st.session_state.history:
            st.button(
                chat["title"],
                key=f"history-{chat['thread_id']}",
                help=chat["title"],
                width='stretch',
                on_click=open_chat,
                args=(chat["thread_id"],),
            )
    else:
        st.caption("Your previous chats will appear here.")

    st.markdown('<div class="section-label">Your data</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "Upload a CSV",
        type=["csv"],
        label_visibility="collapsed",
        key=f"uploaded_file_{st.session_state.upload_widget_key}",
    )
    if uploaded:
        st.caption(f"Ready to use: {uploaded.name}")
    else:
        st.caption("Upload a CSV to start a transformation.")

    st.markdown('<div class="section-label">How it works</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="workflow-step"><span>1</span><div><strong>Describe</strong>'
        "<small>Tell ETLix what you want to do.</small></div></div>"
        '<div class="workflow-step"><span>2</span><div><strong>Review</strong>'
        "<small>See the generated code and preview.</small></div></div>"
        '<div class="workflow-step"><span>3</span><div><strong>Transform</strong>'
        "<small>Load your clean data.</small></div></div>",
        unsafe_allow_html=True,
    )



info = st.session_state.get("info")
completion = st.session_state.get("completion")
answer = st.session_state.get("answer")
has_response = bool(answer or info or st.session_state.get("error") or completion)

if has_response:
    if answer:
        st.divider()
        st.subheader("Answer")
        st.write(answer["explanation"])
        st.dataframe(pd.DataFrame(answer["rows"]), width="stretch")
        with st.expander("Show the generated code"):
            st.code(answer["code"], language="python")

    if info:
        st.divider()
        st.subheader("Review your transformation")
        st.write(info["explanation"])
        if "table_name_input" not in st.session_state:
            st.session_state.table_name_input = info["table_name"]
        table_name = st.text_input(
            "MySQL table name",
            key="table_name_input",
            help="Use a lowercase name starting with a letter; letters, digits, and underscores only (63 characters max).",
        )
        st.subheader("Code written by ETLix")
        st.code(info["code"], language="python")
        st.subheader(f"Preview ({info['row_count']} rows) -> table `{table_name}`")
        st.dataframe(pd.DataFrame(info["preview"]), width='stretch')
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button("Confirm and load", type="primary", width='stretch'):
                try:
                    validate_table_name(table_name)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state.completion = agent.resume(
                        st.session_state.thread_id,
                        approved=True,
                        table_name=table_name,
                    )
                    st.session_state.completion_table_name = table_name
                    st.session_state.info = None
                    save_current_chat()
                    st.rerun()
        with cancel_col:
            if st.button("Cancel", width='stretch'):
                st.session_state.completion = agent.resume(
                    st.session_state.thread_id,
                    approved=False,
                    table_name=table_name,
                )
                st.session_state.completion_table_name = table_name
                st.session_state.info = None
                save_current_chat()
                st.rerun()
    elif st.session_state.get("error"):
        st.error(f"Could not produce a valid transform: {st.session_state.error}")

    if completion:
        if completion.get("status") == "loaded":
            st.success(
                f"Loaded data into MySQL table `{st.session_state.completion_table_name}`."
            )
        elif completion.get("status") == "Cancelled":
            st.info("The transformation was cancelled; nothing was loaded.")
        elif completion.get("status") == "failed":
            st.error(f"Could not load the transformed data: {completion.get('error')}")
else:
    hero_image, hero_copy = st.columns([1, 2.8], vertical_alignment="center")
    with hero_image:
        st.markdown(
            f'<div class="hero-art"><img src="data:image/gif;base64,{BOT_IMAGE_DATA}" '
            'alt="ETLix robot"></div>',
            unsafe_allow_html=True,
        )
    with hero_copy:
        st.markdown(
            '<div class="hero"><h1>Ready to <span>transform</span> your data?</h1>'
            "<p>Upload a CSV and tell ETLix what you would like to do.</p></div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="section-label quick-label"><span>✦</span> Try a quick transformation</div>',
        unsafe_allow_html=True,
    )
    cards = st.columns(len(QUICK))
    quick_icons = (
                '<i class="fa-solid fa-trash fa-xs" style="color: rgb(10, 140, 242);"></i>',
                '<i class="fa-solid fa-chart-bar fa-sm" style="color: rgb(237, 110, 1);"></i>',
                "Σ",
                '<i class="fa-solid fa-chart-simple" style="color: rgb(17, 235, 169);"></i>',
    )
    for index, (col, (label, text)) in enumerate(zip(cards, QUICK.items())):
        with col:
            with st.container(border=True):
                st.markdown(
                    f'<div class="quick-icon quick-icon-{index}">{quick_icons[index]}</div>'
                    f'<div class="quick-title">{label}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(text)
                if st.button("Run this  →", key=f"quick-{label}", width="stretch"):
                    run_instruction(text, uploaded)
                    if uploaded is not None:
                        st.rerun()

if uploaded:
    try:
        uploaded_data = pd.read_csv(io.BytesIO(uploaded.getvalue()))
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        st.error(f"Could not preview the uploaded CSV: {exc}")
    else:
        with st.container(border=True):
            preview_title, preview_meta = st.columns([3, 2], vertical_alignment="center")
            with preview_title:
                st.markdown(
                    '<div class="preview-heading"><span>▤</span> Your data preview</div>',
                    unsafe_allow_html=True,
                )
            with preview_meta:
                st.markdown(
                    f'<div class="preview-meta">{len(uploaded_data):,} rows × '
                    f'{len(uploaded_data.columns):,} columns</div>',
                    unsafe_allow_html=True,
                )
            st.caption(uploaded.name)
            st.dataframe(uploaded_data.head(3), use_container_width=True, hide_index=True)

with st.container(border=True):
    with st.form(
        f"prompt-form-{st.session_state.prompt_widget_key}",
        clear_on_submit=True,
    ):
        icon_col, input_col = st.columns([0.45, 8], vertical_alignment="center")
        with icon_col:
            st.markdown('<div class="prompt-mark">✦</div>', unsafe_allow_html=True)
        with input_col:
            custom = st.text_area(
                "Describe your transformation",
                placeholder="Ask anything about your data...",
                label_visibility="collapsed",
                height=72,
                key=f"custom_prompt_{st.session_state.prompt_widget_key}",
            )
        prompt_col, run_col = st.columns([5, 1])
        with prompt_col:
            st.markdown(
                '<div class="privacy-note"><span>♢</span> Your data stays in your '
                "workflow. Review every change before loading.</div>",
                unsafe_allow_html=True,
            )
        with run_col:
            submitted = st.form_submit_button(
                "➤",
                
                width='stretch',
                key="run-custom",
            )
    if submitted:
        if custom.strip():
            run_instruction(custom.strip(), uploaded)
            if uploaded is not None:
                st.rerun()
        else:
            st.warning("Describe the transformation you want to run.")
