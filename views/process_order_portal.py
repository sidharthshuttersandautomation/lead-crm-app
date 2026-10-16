"""views/process_order_portal.py - Orders for won deals, from PO to installation."""
import streamlit as st

from components.kpi_cards import page_title, render_kpi_cards
from config.settings import DISPATCH_STATUSES, DRAWING_STATUSES, MEASUREMENT_STATUSES, PRODUCTION_STATUSES
from utils.metrics import inr, latest_quotes
from utils.payments import payment_status
from utils.time_utils import now_str


def _idx(options, value):
    return options.index(value) if value in options else 0


def render_process_portal(db_adapter, current_user):
    page_title("Order fulfilment", "Done deals become orders once the PO & PI team claims and checks the PO.")

    df_orders = db_adapter.fetch_all("orders")
    df_leads = db_adapter.fetch_all("leads_master")
    lq = latest_quotes(db_adapter.fetch_all("quotations_master"))

    won = df_leads[df_leads["final_status"] == "Done"] if not df_leads.empty else df_leads
    if not df_orders.empty and not won.empty:
        won = won[~won["lead_id"].isin(df_orders["lead_id"])]
    in_progress = df_orders[df_orders["dispatch_status"] != "Installed"] if not df_orders.empty else df_orders
    render_kpi_cards([
        {"label": "Done deals without an order", "value": len(won), "icon": "🆕", "tone": "amber",
         "sub": "created in PO & payments"},
        {"label": "Orders in progress", "value": len(in_progress), "icon": "🏭", "tone": "blue"},
        {"label": "In production", "value": int((df_orders["production_status"] == "In Production").sum()) if len(df_orders) else 0,
         "icon": "⚙️", "tone": "navy"},
        {"label": "Ready to dispatch", "value": int((df_orders["dispatch_status"] == "Ready").sum()) if len(df_orders) else 0,
         "icon": "🚚", "tone": "green"},
        {"label": "Balance to collect", "value": inr(df_orders["balance"].clip(lower=0).sum()) if len(df_orders) else "₹0",
         "icon": "💰", "tone": "red"},
    ])

    st.caption("New orders are created in 🧾 PO & payments once the client's Process Order is received and checked.")
    tab_update, tab_all = st.tabs(["Update order", "All orders"])

    with tab_update:
        if df_orders.empty:
            st.info("No orders yet.")
        else:
            labels = dict(zip(df_orders["order_id"] + " · " + df_orders["client_name"], df_orders["order_id"]))
            choice = st.selectbox("Order", list(labels.keys()))
            order = df_orders[df_orders["order_id"] == labels[choice]].iloc[0]
            render_kpi_cards([
                {"label": "Order value", "value": inr(order["order_value"]), "tone": "blue"},
                {"label": "Received", "value": inr(order["received"]), "tone": "green"},
                {"label": "Balance", "value": inr(max(order["balance"], 0)), "tone": "red"},
                {"label": "Payment", "value": payment_status(order["order_value"], order["received"]), "tone": "navy"},
            ])
            st.caption(f"{order['product']} × {order['qty']} · quote {order.get('quotation_ref') or '—'} · "
                       f"sales: {order.get('sales_person') or '—'}")
            with st.form(f"update_order_{order['order_id']}"):
                c1, c2 = st.columns(2)
                with c1:
                    measurement = st.selectbox("Measurement", MEASUREMENT_STATUSES, index=_idx(MEASUREMENT_STATUSES, order["measurement_status"]))
                    drawing = st.selectbox("Drawing", DRAWING_STATUSES, index=_idx(DRAWING_STATUSES, order["drawing_status"]))
                with c2:
                    production = st.selectbox("Production", PRODUCTION_STATUSES, index=_idx(PRODUCTION_STATUSES, order["production_status"]))
                    dispatch = st.selectbox("Dispatch", DISPATCH_STATUSES, index=_idx(DISPATCH_STATUSES, order["dispatch_status"]))
                remarks = st.text_area("Remarks", value=order.get("remarks") or "")
                if st.form_submit_button("Save changes"):
                    updates = {"measurement_status": measurement, "drawing_status": drawing,
                               "production_status": production, "dispatch_status": dispatch,
                               "remarks": remarks.strip() or None, "updated_at": now_str()}
                    # keep the payment tracker in step with dispatch / installation
                    if dispatch in ("Dispatched", "Installed") and not order.get("dispatched_at"):
                        updates["dispatched_at"] = now_str()
                    if dispatch == "Installed" and not order.get("installed_at"):
                        updates["installed_at"] = now_str()
                    if db_adapter.update_row("orders", "order_id", order["order_id"], updates):
                        st.toast(f"{order['order_id']} updated.", icon="✅")
                        st.rerun()
                    else:
                        st.error(db_adapter.last_error)

    with tab_all:
        if df_orders.empty:
            st.info("No orders yet.")
        else:
            st.dataframe(df_orders.drop(columns=["lead_id", "assigned_sam_id"], errors="ignore"),
                         width="stretch", hide_index=True)
