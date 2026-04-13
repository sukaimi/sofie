"""Streamlit operator dashboard — job approval interface for Noel.

Single page showing pending jobs with previews, QA scores, cost,
and approve/reject/extend-budget actions. Functional, not beautiful.
"""

import requests
import streamlit as st

API_BASE = "http://backend:8000"

st.set_page_config(page_title="SOFIE — Operator Dashboard", layout="wide")
st.title("SOFIE — Operator Dashboard")


def fetch_jobs() -> list[dict]:
    """Pull pending jobs from the backend API."""
    try:
        resp = requests.get(f"{API_BASE}/operator/jobs", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"Cannot reach backend: {exc}")
        return []


def approve_job(job_id: str) -> None:
    """Send approval to backend."""
    try:
        resp = requests.post(f"{API_BASE}/operator/jobs/{job_id}/approve", timeout=10)
        resp.raise_for_status()
        st.success(f"Job {job_id} approved")
    except Exception as exc:
        st.error(f"Approval failed: {exc}")


def reject_job(job_id: str, notes: str) -> None:
    """Send rejection with notes to backend."""
    try:
        resp = requests.post(
            f"{API_BASE}/operator/jobs/{job_id}/reject",
            json={"notes": notes},
            timeout=10,
        )
        resp.raise_for_status()
        st.success(f"Job {job_id} sent back for revision")
    except Exception as exc:
        st.error(f"Rejection failed: {exc}")


def extend_budget(job_id: str) -> None:
    """Extend cost ceiling by $1.00."""
    try:
        resp = requests.post(
            f"{API_BASE}/operator/jobs/{job_id}/extend-budget", timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        st.success(f"Budget extended to ${data.get('new_ceiling', '?'):.2f}")
    except Exception as exc:
        st.error(f"Budget extension failed: {exc}")


# ── Main UI ───────────────────────────────────────────────────────────

if st.button("Refresh"):
    st.rerun()

jobs = fetch_jobs()

if not jobs:
    st.info("No pending jobs.")
else:
    for job in jobs:
        job_id = job["job_id"]

        with st.container():
            st.divider()
            col1, col2 = st.columns([2, 1])

            with col1:
                st.subheader(f"{job['brand_name']} — {job['job_title']}")
                st.caption(f"Job ID: {job_id} | Status: {job['status']}")
                st.caption(f"Created: {job.get('created_at', 'Unknown')}")

                # Output previews
                output_paths = job.get("output_paths", {})
                if output_paths:
                    for size, path in output_paths.items():
                        filename = path.split("/")[-1]
                        img_url = f"{API_BASE}/job/{job_id}/download/{filename}"
                        st.image(img_url, caption=size, use_container_width=True)

            with col2:
                # QA scores
                qa = job.get("qa_results", {})
                if qa:
                    st.markdown("**QA Scores**")
                    for check_key, label in [
                        ("check1_layout", "Layout"),
                        ("check2_brief", "Brief"),
                        ("check3_spec", "Spec"),
                    ]:
                        check = qa.get(check_key, {})
                        score = check.get("score", 0)
                        passed = check.get("pass", False)
                        icon = "+" if passed else "-"
                        st.markdown(f"- {label}: **{score}**/100 {icon}")
                        issues = check.get("issues", [])
                        for issue in issues:
                            st.caption(f"  - {issue}")

                # Cost
                cost = job.get("total_cost_usd", 0)
                st.metric("Cost", f"${cost:.4f}")

                # Actions
                st.markdown("---")

                if st.button("Approve", key=f"approve_{job_id}"):
                    approve_job(job_id)
                    st.rerun()

                notes = st.text_area(
                    "Rejection notes",
                    key=f"notes_{job_id}",
                    placeholder="Describe what needs to change...",
                )
                if st.button("Reject", key=f"reject_{job_id}"):
                    if notes:
                        reject_job(job_id, notes)
                        st.rerun()
                    else:
                        st.warning("Please add rejection notes")

                if job["status"] == "escalated" and "cost" in str(
                    job.get("qa_results", {})
                ):
                    if st.button("Extend Budget (+$1)", key=f"extend_{job_id}"):
                        extend_budget(job_id)
                        st.rerun()
