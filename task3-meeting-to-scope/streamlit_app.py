"""Streamlit Web UI for Task 3 — Meeting to Scope.

Run with:
    streamlit run streamlit_app.py --server.port 8502
"""

import os
import json
import httpx
import streamlit as st

st.set_page_config(
    page_title="Meeting to Scope — AI Tech Consultant",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #10b981, #3b82f6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .badge-feasibility {
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .feasibility-config { background-color: #10b98133; color: #34d399; }
    .feasibility-limit { background-color: #f59e0b33; color: #fbbf24; }
    .feasibility-custom { background-color: #8b5cf633; color: #c084fc; }
    .feasibility-clarify { background-color: #ef444433; color: #f87171; }
    </style>
    """,
    unsafe_allow_html=True,
)

API_BASE = os.getenv("T3_BASE_URL", "http://localhost:8002")


def call_t3_api(method: str, path: str, json_data: dict = None) -> dict:
    url = f"{API_BASE}{path}"
    try:
        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                resp = client.get(url)
            else:
                resp = client.post(url, json=json_data)
            return {"status_code": resp.status_code, "data": resp.json()}
    except Exception as e:
        return {"status_code": 500, "error": str(e)}


# ── Sidebar ─────────────────────────────────────────────────
with st.sidebar:
    st.title("📋 Meeting to Scope")
    st.caption("Multi-Agent Scope & Proposal Engine")
    st.divider()

    st.subheader("⚙️ System Status")
    health = call_t3_api("GET", "/health")
    if health.get("status_code") == 200:
        st.success("API Server: Online (8002)")
    else:
        st.warning("API Server Offline (using local modules directly)")

    st.divider()
    st.subheader("💵 Commercial Settings")
    hourly_rate = st.number_input("Consultant Hourly Rate ($/hr)", min_value=50, max_value=500, value=150)
    currency = st.selectbox("Currency", ["USD", "GBP", "EUR"], index=0)


# ── Tabs ────────────────────────────────────────────────────
tab_pipeline, tab_approval, tab_diff = st.tabs([
    "🚀 5-Agent Analysis Pipeline",
    "🔒 Human Approval Gate",
    "🔄 Follow-Up Scope Diff (Transcript C vs A)",
])

# ── Tab 1: Pipeline ─────────────────────────────────────────
with tab_pipeline:
    st.markdown('<div class="main-title">Multi-Agent Meeting to Scope</div>', unsafe_allow_html=True)
    st.caption("Extract requirements, verify feasibility against Task 1, generate scope, hours estimate, and proposal.")

    t_api_res = call_t3_api("GET", "/api/transcripts")
    if t_api_res.get("status_code") == 200 and t_api_res.get("data"):
        transcripts = t_api_res["data"]
    else:
        transcripts = [
            {"id": "transcript_a", "label": "Transcript A — Local Lawyers Directory (Initial)"},
            {"id": "transcript_b", "label": "Transcript B — Artisan Bakers Guild (E-commerce)"},
            {"id": "transcript_c", "label": "Transcript C — Lawyers Directory (Follow-Up Meeting)"},
        ]
        user_dir = os.path.join(os.path.dirname(__file__), "transcripts_user")
        if os.path.exists(user_dir):
            for uf in sorted(os.listdir(user_dir)):
                if uf.endswith(".txt"):
                    stem = uf[:-4]
                    transcripts.append({"id": stem, "label": f"📁 User: {stem.replace('_', ' ').title()}"})

    selected_t = st.selectbox(
        "Select Meeting Transcript:",
        options=transcripts,
        format_func=lambda x: str(x.get("label", x.get("id"))),
    )

    # Load and show transcript preview
    t_id = selected_t["id"]
    t_path = os.path.join(os.path.dirname(__file__), "transcripts", f"{t_id}.json")
    ut_path = os.path.join(os.path.dirname(__file__), "transcripts_user", f"{t_id}.txt")

    if os.path.exists(t_path):
        with open(t_path, "r", encoding="utf-8") as f:
            t_data = json.load(f)

        with st.expander(f"📜 View Raw Transcript: {t_data.get('project_name')} ({len(t_data.get('dialogue', []))} turns)"):
            st.write(f"**Client:** {t_data.get('client_name')} ({t_data.get('client_role')})")
            st.write(f"**Consultant:** {t_data.get('consultant_name')} ({t_data.get('consultant_role')})")
            st.write(f"**Meeting Date:** {t_data.get('meeting_date')}")
            st.divider()
            for turn in t_data.get("dialogue", []):
                st.markdown(f"**[{turn.get('timestamp')}] {turn.get('speaker')}:** {turn.get('text')}")
    elif os.path.exists(ut_path):
        from agents.transcript_analyst import parse_transcript_text
        with open(ut_path, "r", encoding="utf-8") as f:
            u_text = f.read()
        u_dialogue = parse_transcript_text(u_text)
        with st.expander(f"📁 View User Transcript: {t_id.replace('_', ' ').title()} ({len(u_dialogue)} parsed turns)"):
            st.caption(f"Source file: `transcripts_user/{t_id}.txt`")
            st.divider()
            for turn in u_dialogue:
                st.markdown(f"**[{turn.get('timestamp')}] {turn.get('speaker')}:** {turn.get('text')}")

    if st.button("🚀 Run 5-Agent Pipeline on Selected Transcript", type="primary"):
        with st.spinner("Executing: Transcript Analyst → Product Feasibility (Task 1) → Scope Agent → Estimation Agent → Proposal Agent..."):
            # Execute pipeline
            res = call_t3_api("POST", f"/api/transcripts/{t_id}/analyze")
            if res.get("status_code") != 200:
                # Local fallback execution
                from app.routes.analysis import analyze_transcript
                import asyncio
                data = asyncio.run(analyze_transcript(t_id))
            else:
                data = res["data"]

            st.session_state[f"analysis_{t_id}"] = data
            st.success("All 5 Agents Completed Successfully!")

    # Display Analysis Results if available in session
    if f"analysis_{t_id}" in st.session_state:
        data = st.session_state[f"analysis_{t_id}"]

        if data.get("extraction_mode") == "offline_heuristic":
            st.warning(
                "⚠️ DEGRADED EXTRACTION MODE (Offline Heuristic): Results were generated using rule-based "
                "offline extraction because LLM was unavailable or quota was exhausted. Natural wording, "
                "negations, and complex statements are degraded."
            )

        # 1. Requirements & Feasibility
        st.subheader("1. Extracted Requirements & Platform Feasibility")
        reqs = data.get("requirements", [])
        for r in reqs:
            feas = r.get("feasibility", "needs_clarification")
            badge_class = (
                "feasibility-config" if feas == "existing_config"
                else "feasibility-limit" if feas == "existing_feature_with_limitation"
                else "feasibility-custom" if feas == "potential_custom"
                else "feasibility-clarify"
            )
            with st.container():
                st.markdown(
                    f"**{r.get('id')}: {r.get('description')}** "
                    f'<span class="badge-feasibility {badge_class}">{feas.replace("_", " ").upper()}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"> *Quote: {r.get('source_quote')}*")
                st.caption(f"Feasibility Note: {r.get('feasibility_detail')}")
                st.divider()

        # 2. Scope Document
        scope = data.get("scope", {})
        with st.expander("📄 View Formal Scope Document (10 Sections)", expanded=True):
            st.markdown(f"### {scope.get('title')}")
            st.markdown(f"**Objective:** {scope.get('objective')}")
            st.markdown(f"**Current Problem:** {scope.get('current_problem')}")
            st.markdown(f"**Proposed Solution:** {scope.get('proposed_solution')}")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 📦 Deliverables")
                for d in scope.get("deliverables", []):
                    st.markdown(f"- {d}")

                st.markdown("#### 🚫 Exclusions")
                for ex in scope.get("exclusions", []):
                    st.markdown(f"- {ex}")

            with col2:
                st.markdown("#### ✅ Acceptance Criteria")
                for ac in scope.get("acceptance_criteria", []):
                    st.markdown(f"- {ac}")

                st.markdown("#### 👤 Client Duties")
                for cd in scope.get("client_responsibilities", []):
                    st.markdown(f"- {cd}")

            st.info(f"Target Delivery Milestone: **{scope.get('target_delivery_date')}** | Status: **{scope.get('status').upper()}**")

        # 3. Estimates
        est = data.get("estimate", {})
        with st.expander("⏱️ Hours & Pricing Breakdown", expanded=True):
            tasks = est.get("tasks", [])
            table_rows = [
                {
                    "Task": t.get("name"),
                    "Low (hrs)": t.get("low_hours"),
                    "Likely (hrs)": t.get("likely_hours"),
                    "High (hrs)": t.get("high_hours"),
                    "Reasoning": t.get("reasoning"),
                }
                for t in tasks
            ]
            st.dataframe(table_rows, use_container_width=True)

            c1, c2, c3 = st.columns(3)
            c1.metric("Low Estimate", f"{est.get('total_low_hours'):.1f} hrs", f"${est.get('estimated_cost_low'):,.2f}")
            c2.metric("Likely Estimate", f"{est.get('total_likely_hours'):.1f} hrs", f"${est.get('estimated_cost_likely'):,.2f}")
            c3.metric("High Estimate", f"{est.get('total_high_hours'):.1f} hrs", f"${est.get('estimated_cost_high'):,.2f}")

        # 4. Proposal Preview
        prop = data.get("proposal", {})
        with st.expander("📝 Client Technical Proposal Preview"):
            st.markdown(f"## {prop.get('title')}")
            st.write(prop.get("executive_summary"))
            st.markdown("### Pricing Breakdown")
            st.text(prop.get("pricing_breakdown"))
            st.markdown("### Next Steps")
            for ns in prop.get("next_steps", []):
                st.write(ns)


# ── Tab 2: Approval Gate ────────────────────────────────────
with tab_approval:
    st.subheader("🔒 Human Approval Gate")
    st.markdown("PRD Requirement: Proposals and Scope baselines MUST be approved by an authorized reviewer before sending or diffing.")

    scope_id_input = st.text_input("Scope Version ID to Approve:", value="scope-proj_lawyers_directory-v1")
    reviewer_input = st.text_input("Reviewer Name:", value="Emily Watson (Managing Director)")

    if st.button("✅ Formally Approve Scope Baseline", type="primary"):
        with st.spinner("Recording approval in audit log..."):
            res = call_t3_api(
                "POST",
                "/api/projects/proj_lawyers_directory/approve",
                {"scope_version_id": scope_id_input, "reviewer": reviewer_input},
            )
            if res.get("status_code") == 200:
                st.success(f"Scope '{scope_id_input}' has been approved by {reviewer_input}!")
                st.session_state["baseline_approved"] = True
            else:
                st.error(f"Approval failed: {res}")


# ── Tab 3: Follow-Up Scope Diff ─────────────────────────────
with tab_diff:
    st.subheader("🔄 Follow-Up Scope Diff (Transcript C vs Baseline A)")
    st.markdown("Compares follow-up meeting modifications strictly against the **APPROVED** baseline scope.")

    baseline_id = st.text_input("Approved Baseline Scope ID:", value="scope-proj_lawyers_directory-v1")

    if st.button("🔍 Run Scope Diff against Approved Baseline"):
        with st.spinner("Analyzing Transcript C modifications vs approved baseline..."):
            res = call_t3_api(
                "POST",
                "/api/projects/proj_lawyers_directory/compare",
                {"baseline_scope_id": baseline_id, "follow_up_transcript_id": "transcript_c"},
            )

            if res.get("status_code") == 200:
                diff_data = res["data"]
                report = diff_data["diff_report"]
                st.success("Scope Diff Generated Successfully!")

                st.markdown("### 📋 Change Report Summary")
                ext_mode = report.get("extraction_mode", "llm")
                if ext_mode == "offline_heuristic" or diff_data.get("extraction_mode") == "offline_heuristic":
                    st.warning(
                        "⚠️ DEGRADED EXTRACTION MODE (Offline Heuristic): Follow-up diff was performed using "
                        "rule-based offline extraction because LLM was unavailable. Nuanced intent matching is degraded."
                    )
                mode_badge = "🤖 Extraction Mode: LLM Grounded" if ext_mode == "llm" else "⚙️ Extraction Mode: Offline Heuristic Rule-Based"
                st.caption(mode_badge)
                st.text(report.get("summary"))

                c1, c2, c3 = st.columns(3)
                c1.metric("Added Requirements", len(report.get("added_requirements", [])), "Twilio SMS 2FA")
                c2.metric("Removed Requirements", len(report.get("removed_requirements", [])), "Mass Email Setup")
                c3.metric("Net Effort Delta", f"{report.get('hours_delta'):+.1f} hrs", f"${report.get('cost_delta'):+,.2f} USD")

                st.info(f"📅 Timeline Change: {report.get('timeline_delta')}")

                rev_scope = diff_data.get("revised_scope", {})
                st.subheader(f"📄 Revised Scope: {rev_scope.get('title')}")
                st.write(f"Target Milestone: **{rev_scope.get('target_delivery_date')}**")
                for d in rev_scope.get("deliverables", []):
                    st.write(f"- {d}")
            else:
                st.error(f"Diff execution failed: {res.get('error', res.get('data'))}")
