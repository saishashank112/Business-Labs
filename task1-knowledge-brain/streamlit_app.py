"""Streamlit Web UI for Knowledge Brain (Task 1).

Run with:
    streamlit run streamlit_app.py --server.port 8501
"""

import os
import sys
import json
import asyncio
import httpx
import streamlit as st

# Configure page
st.set_page_config(
    page_title="Knowledge Brain — AI Tech Consultant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for modern styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #94a3b8;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .source-card {
        padding: 0.8rem 1rem;
        border-radius: 8px;
        border: 1px solid #334155;
        background-color: #1e293b;
        margin-bottom: 0.5rem;
    }
    .badge-evidence {
        background-color: #10b981;
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
    }
    .badge-insufficient {
        background-color: #ef4444;
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Read API base URL and key from env
API_BASE = os.getenv("T1_BASE_URL", "http://localhost:8001")
API_KEY = os.getenv("T1_API_KEY", "change-me-in-production")


# Helper function to call backend API
def call_api(method: str, path: str, json_data: dict = None) -> dict:
    url = f"{API_BASE}{path}"
    headers = {"X-API-Key": API_KEY}
    try:
        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                resp = client.get(url, headers=headers)
            else:
                resp = client.post(url, headers=headers, json=json_data)
            return {"status_code": resp.status_code, "data": resp.json()}
    except Exception as e:
        return {"status_code": 500, "error": str(e)}


# ── Sidebar ─────────────────────────────────────────────────
with st.sidebar:
    st.title("🧠 Knowledge Brain")
    st.caption("Brilliant Directories AI Consultant")

    st.divider()
    st.subheader("⚙️ System Status")

    # Health check
    health_res = call_api("GET", "/health")
    if health_res.get("status_code") == 200:
        st.success("API Server: Online (8001)")
        db_stat = health_res["data"].get("db", "unknown")
        st.write(f"**Database:** `{db_stat}`")
        uptime = int(health_res["data"].get("uptime_seconds", 0))
        st.write(f"**Uptime:** `{uptime}s`")
    else:
        st.error(f"API Server Offline: {health_res.get('error', 'Cannot connect')}")

    st.divider()
    st.subheader("🔍 Retrieval Settings")
    search_mode = st.selectbox(
        "Search Mode",
        options=["hybrid", "vector", "keyword"],
        index=0,
        help="Hybrid uses both ChromaDB embeddings and SQLite FTS5 with Reciprocal Rank Fusion",
    )

    st.divider()
    st.subheader("🕷️ Ingestion Pipeline")
    max_pages = st.number_input("Max Pages to Crawl", min_value=1, max_value=100, value=10)
    if st.button("🚀 Run Ingestion Crawl", use_container_width=True):
        with st.spinner("Starting crawl job..."):
            crawl_res = call_api("POST", "/ingestion/run", {"max_pages": max_pages})
            if crawl_res.get("status_code") in (200, 202):
                st.success("Ingestion job started in background!")
            else:
                st.error(f"Failed to start ingestion: {crawl_res}")

    if st.button("📊 Check Ingestion Status", use_container_width=True):
        status_res = call_api("GET", "/ingestion/status")
        if status_res.get("status_code") == 200:
            st.json(status_res["data"])


# ── Main Content Tabs ───────────────────────────────────────
tab_query, tab_escalations, tab_logs = st.tabs(["💬 Query Knowledge Base", "🚨 Escalations (HITL)", "📈 LLM Logs"])

# ── Tab 1: Query Knowledge Base ─────────────────────────────
with tab_query:
    st.markdown('<div class="main-header">Knowledge Brain Assistant</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Ask technical questions regarding Brilliant Directories. Answers are grounded strictly in official documentation.</div>', unsafe_allow_html=True)

    # Example question chips
    col1, col2, col3 = st.columns(3)
    if col1.button("📧 Mass Email Campaigns", use_container_width=True):
        st.session_state["sample_q"] = "Can I send a mass email campaign using Brilliant Directories?"
    if col2.button("📂 Category CSV Import", use_container_width=True):
        st.session_state["sample_q"] = "How do I import categories via CSV file?"
    if col3.button("✉️ Email Forwarders Setup", use_container_width=True):
        st.session_state["sample_q"] = "How do email forwarders work?"

    query_input = st.text_input(
        "Your technical question:",
        value=st.session_state.get("sample_q", ""),
        placeholder="e.g. How do I configure email forwarders?",
    )

    if st.button("Ask Knowledge Brain", type="primary"):
        if not query_input.strip():
            st.warning("Please enter a question.")
        else:
            with st.spinner(f"Retrieving evidence ({search_mode} mode) and generating cited answer..."):
                res = call_api(
                    "POST",
                    "/query",
                    {"question": query_input, "mode": search_mode},
                )

                if res.get("status_code") == 200:
                    data = res["data"]
                    status = data.get("status", "answered")

                    if status == "answered":
                        st.markdown('### Answer <span class="badge-evidence">Evidence Verified</span>', unsafe_allow_html=True)
                        st.markdown(data.get("answer", ""))
                    else:
                        st.markdown('### Answer <span class="badge-insufficient">Needs Human Expert</span>', unsafe_allow_html=True)
                        st.warning(data.get("answer", ""))
                        if data.get("escalation_id"):
                            st.info(f"An escalation task has been created for human review (ID: `{data['escalation_id']}`)")

                    # Sources cited
                    sources = data.get("sources", [])
                    if sources:
                        st.markdown("#### 📚 Sources Cited")
                        for s in sources:
                            rel_str = f" (Relevance: {int(s['relevance']*100)}%)" if s.get("relevance") else ""
                            st.markdown(f"- 📄 [{s['title']}]({s['url']}){rel_str}")

                    # Images
                    images = data.get("images", [])
                    if images:
                        st.markdown("#### 🖼️ Screenshot References")
                        for img in images:
                            st.image(img["url"], caption=img.get("description", "Documentation Screenshot"), width=400)
                else:
                    st.error(f"Error querying backend: {res.get('error', res.get('data'))}")


# ── Tab 2: Escalations (Human-in-the-Loop) ───────────────────
with tab_escalations:
    st.subheader("🚨 Unresolved Inquiries & Escalations")
    st.markdown("When evidence is missing or contradictory, questions are routed here. Human-verified answers are ingested to continuously train the Brain.")

    esc_res = call_api("GET", "/escalations")
    if esc_res.get("status_code") == 200:
        escalations = esc_res["data"]
        open_items = [e for e in escalations if e.get("status") == "open"]
        resolved_items = [e for e in escalations if e.get("status") == "resolved"]

        st.metric("Open Escalations", len(open_items), delta=f"{len(resolved_items)} resolved")

        if open_items:
            for esc in open_items:
                with st.expander(f"🔴 OPEN: {esc['question'][:80]}...", expanded=True):
                    st.write(f"**Question:** {esc['question']}")
                    st.write(f"**Reason:** {esc.get('reason') or 'Unspecified'}")
                    if esc.get("evidence"):
                        st.text_area("Retrieved Evidence (Partial)", esc["evidence"], height=100, disabled=True, key=f"ev_{esc['id']}")

                    # Resolution Form
                    with st.form(key=f"form_{esc['id']}"):
                        expert_answer = st.text_area("Human Verified Answer:", placeholder="Provide the verified steps or explanation...")
                        reviewer_name = st.text_input("Reviewer Name:", value="Expert Consultant")
                        submit = st.form_submit_button("✅ Resolve & Feed into Brain")

                        if submit:
                            if not expert_answer.strip():
                                st.error("Please enter a verified answer.")
                            else:
                                resolve_res = call_api(
                                    "POST",
                                    f"/escalations/{esc['id']}/resolve",
                                    {"answer": expert_answer, "reviewer": reviewer_name},
                                )
                                if resolve_res.get("status_code") == 200:
                                    st.success(f"Resolved! Ingested as Knowledge ID: `{resolve_res['data'].get('knowledge_id')}`")
                                    st.rerun()
                                else:
                                    st.error(f"Failed to resolve: {resolve_res}")
        else:
            st.info("No open escalations! All queries have either been answered with evidence or resolved by experts.")

        if resolved_items:
            st.divider()
            st.markdown("#### ✅ Resolved History")
            for esc in resolved_items[:5]:
                with st.expander(f"🟢 Resolved: {esc['question'][:80]}"):
                    st.write(f"**Resolver:** {esc.get('resolver')}")
                    st.write(f"**Resolved At:** {esc.get('resolved_at')}")
    else:
        st.warning("Could not load escalations from server.")


# ── Tab 3: LLM Logs & Cost Audit ────────────────────────────
with tab_logs:
    st.subheader("📈 LLM Call & Cost Logs")
    st.markdown("Tracks all LLM invocations, token counts, latencies, and estimated USD costs.")

    # Query sqlite llm_log table directly
    try:
        import sqlite3
        con = sqlite3.connect("task1.db")
        cur = con.cursor()
        cur.execute("SELECT id, request_id, step, model, provider, input_tokens, output_tokens, latency_ms, cost_usd, timestamp FROM llm_log ORDER BY id DESC LIMIT 50")
        rows = cur.fetchall()
        con.close()

        if rows:
            table_data = [
                {
                    "ID": r[0],
                    "Step": r[2],
                    "Model": r[3],
                    "Provider": r[4],
                    "Prompt Tokens": r[5],
                    "Output Tokens": r[6],
                    "Latency (ms)": r[7],
                    "Cost ($)": f"${r[8]:.6f}" if r[8] is not None else "$0.00",
                    "Time": r[9],
                }
                for r in rows
            ]
            st.dataframe(table_data, use_container_width=True)
        else:
            st.info("No LLM calls logged yet. Queries using MockLLMClient or cached responses appear here when active.")
    except Exception as e:
        st.info("No database log table available yet.")
