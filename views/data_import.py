"""views/data_import.py - Load the old lead workbook (Google Sheets export) into the CRM."""
import hashlib

import pandas as pd
import streamlit as st

from components.kpi_cards import page_title, render_kpi_cards
from utils.excel_import import apply_plan, convert_workbook


def render_data_import(db_adapter, current_user):
    page_title("Import from Excel", "Load your existing Leads workbook (Leads Data, Quotation Sheet, "
                                    "Quotation Follow Up Tracker, Process Order) into the CRM.")
    up = st.file_uploader("Workbook (.xlsx)", type=["xlsx"])
    if up is None:
        st.info("Export the Google Sheet as Microsoft Excel (.xlsx) and upload it here. "
                "Nothing is saved until you press Import.")
        return

    data = up.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    if st.session_state.get("import_digest") != digest:
        with st.spinner("Reading and converting the workbook..."):
            try:
                st.session_state["import_plan"] = convert_workbook(up, db_adapter)
                st.session_state["import_digest"] = digest
            except Exception as exc:
                st.error(f"Could not read this file: {exc}")
                return
    plan = st.session_state["import_plan"]
    s = plan["summary"]

    render_kpi_cards([
        {"label": "Leads", "value": s["Leads"], "icon": "📥", "tone": "blue",
         "sub": f"{s['Open']} open · {s['Done']} won · {s['Cancled']} lost"},
        {"label": "Quotations", "value": s["Quotations"], "icon": "📄", "tone": "teal"},
        {"label": "Follow-up calls", "value": s["Follow-up calls"], "icon": "📞", "tone": "amber"},
        {"label": "Orders", "value": s["Orders"], "icon": "🏭", "tone": "green"},
        {"label": "New accounts / products", "value": f"{s['New accounts']} / {s['New products']}", "icon": "➕", "tone": "navy"},
    ])
    st.caption(f"Latest record in the file: {s['Data up to']}")

    with st.expander(f"How the data was converted ({len(plan['notes'])})", expanded=True):
        for n in plan["notes"]:
            st.markdown(f"- {n}")
    if plan["warnings"]:
        with st.expander(f"⚠️ Things to check ({len(plan['warnings'])})"):
            for w in plan["warnings"]:
                st.markdown(f"- {w}")

    preview = pd.DataFrame(plan["leads"]).drop(columns=["_cid", "_pkey"])
    stages = preview["final_status"].value_counts().rename_axis("Stage").reset_index(name="Leads")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown("###### Stages after import")
        st.dataframe(stages, width="stretch", hide_index=True)
    with c2:
        st.markdown("###### Preview")
        st.dataframe(preview[["client_id", "final_status", "quotation_status", "source", "handled_by_lge_id",
                              "assigned_sam_id", "claimed_qs_id", "next_followup_at", "remarks"]].head(50),
                     width="stretch", hide_index=True)

    st.markdown("---")
    existing = db_adapter.count_rows("leads_master")
    replace = st.checkbox(f"Replace existing lead data ({existing} leads, with their quotations, calls, orders "
                          "and payments). Users and products are kept.", value=existing > 0)
    confirm = st.text_input("Type IMPORT to confirm")
    if st.button("Import", disabled=confirm.strip().upper() != "IMPORT"):
        try:
            result = apply_plan(db_adapter, plan, replace)
        except Exception as exc:
            st.error(f"Import stopped: {exc}")
            return
        st.session_state.pop("import_digest", None)
        st.success("Imported: " + ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in result.items() if k != "cleared"))
        st.toast("Import finished. Open the Business tower or Quotation desk to see the data.", icon="✅")
