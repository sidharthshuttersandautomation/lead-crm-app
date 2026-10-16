"""components/target_gauges.py - Row of target gauges for one employee and month."""
import streamlit as st

from utils.targets import actual, gauge, get_targets, metrics_for


def render_target_gauges(db, emp_id, role, month, data, key_prefix="g", only_with_target=False):
    keys = metrics_for(role)
    targets = get_targets(db, emp_id, month)
    if only_with_target:
        keys = [k for k in keys if targets.get(k)]
    if not keys:
        return targets
    cols = st.columns(min(3, len(keys)))
    for i, k in enumerate(keys):
        with cols[i % len(cols)]:
            st.plotly_chart(gauge(k, actual(k, emp_id, month, data), float(targets.get(k) or 0), month),
                            width="stretch", key=f"{key_prefix}_{emp_id}_{k}")
    st.caption("Green ≥ 90% of target · amber 50–90% · red below 50%. The dark marker shows where you should be by today.")
    return targets
