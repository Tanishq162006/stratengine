"""StratEngine — Streamlit UI for saved strategies.

Three competition tabs (BRAIN, QuantConnect, IMC Prosperity) each show a
sortable list of saved strategies with star rating, status, and the most
recent metric snapshot. Side panel covers add / edit / record-result /
rate / delete. The BRAIN tab inlines the local `wq-check` pre-flight so
the user can sanity-check an expression without leaving the UI.

Launch with:    python3 run.py ui
Or directly:    streamlit run ui_app.py
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

import strategies_db as sdb


COMPETITIONS = sdb.COMPETITIONS
LABELS = sdb.COMPETITION_LABELS
METRIC_VOCAB = sdb.METRIC_VOCAB


def _metric_chips(latest: dict[str, float]) -> str:
    if not latest:
        return "—"
    parts = []
    for k, v in latest.items():
        if isinstance(v, float):
            parts.append(f"{k}: {v:.3f}" if abs(v) < 100 else f"{k}: {v:.1f}")
        else:
            parts.append(f"{k}: {v}")
    return " · ".join(parts)


def _stars(rating: int) -> str:
    rating = max(0, min(5, int(rating or 0)))
    return "★" * rating + "☆" * (5 - rating)


def _wq_check_inline(expression: str) -> tuple[list[str], list[str]]:
    from competitions.worldquant_iqc.plugin import _validate
    warns = _validate(expression)
    return (
        [w for w in warns if w.startswith("ERROR")],
        [w for w in warns if not w.startswith("ERROR")],
    )


def _render_add_strategy(competition: str) -> None:
    with st.expander("➕ Add a strategy", expanded=False):
        with st.form(f"add_{competition}", clear_on_submit=True):
            name = st.text_input("Name", placeholder="e.g. vol-confirmed reversal v3")
            expression = st.text_area(
                "Expression / code",
                height=160,
                placeholder=(
                    "BRAIN: scale(group_neutralize(...))\n"
                    "QC / IMC: paste the algorithm Python here"
                ),
            )
            thesis = st.text_input(
                "Thesis (one line)",
                placeholder="Why this should work in plain English",
            )
            config_text = st.text_area(
                "Config JSON (optional)",
                placeholder='{"decay": 4, "delay": 1, "universe": "TOP3000"}',
                height=80,
            )
            source = st.selectbox(
                "Source",
                options=("manual", "alpha_gpt", "playbook", "imported"),
                index=0,
            )
            submitted = st.form_submit_button("Save")
            if submitted:
                if not name.strip() or not expression.strip():
                    st.error("Name and expression are required.")
                    return
                try:
                    cfg = json.loads(config_text) if config_text.strip() else {}
                except json.JSONDecodeError as e:
                    st.error(f"Config JSON invalid: {e}")
                    return
                sid = sdb.upsert_strategy(
                    competition=competition,
                    name=name.strip(),
                    expression=expression.strip(),
                    thesis=thesis.strip(),
                    config=cfg,
                    source=source,
                )
                st.success(f"Saved · id={sid}")
                st.rerun()


def _render_strategy_row(s: dict, competition: str) -> None:
    rating = int(s.get("rating") or 0)
    status = s.get("status") or "draft"
    latest = sdb.latest_metrics(s["strategy_id"])
    title = f"{_stars(rating)}  **{s['name']}**  · {status}"
    with st.expander(title, expanded=False):
        st.code(s["expression"], language="text")
        if s.get("thesis"):
            st.markdown(f"**Thesis** · {s['thesis']}")
        if s.get("config"):
            st.markdown(f"**Config** · `{json.dumps(s['config'])}`")
        if latest:
            st.markdown(f"**Last results** · {_metric_chips(latest)}")
        st.caption(
            f"id `{s['strategy_id']}`  · source `{s.get('source','?')}`  · "
            f"competition `{LABELS.get(competition, competition)}`"
        )

        # Inline wq-check for BRAIN
        if competition == "worldquant_iqc":
            if st.button("Run wq-check", key=f"wqc_{s['strategy_id']}"):
                blockers, advisories = _wq_check_inline(s["expression"])
                if blockers:
                    st.error("Blockers:\n\n" + "\n\n".join(f"- {b}" for b in blockers))
                else:
                    st.success("Syntax: clean.")
                if advisories:
                    st.warning("Advisories:\n\n" + "\n\n".join(f"- {a}" for a in advisories))

        st.divider()

        col_rating, col_status = st.columns([2, 2])
        with col_rating:
            new_rating = st.slider(
                "Star rating",
                0, 5, rating,
                key=f"rate_{s['strategy_id']}",
            )
        with col_status:
            new_status = st.selectbox(
                "Status",
                options=sdb.STATUS_VALUES,
                index=sdb.STATUS_VALUES.index(status) if status in sdb.STATUS_VALUES else 0,
                key=f"status_{s['strategy_id']}",
            )
        new_notes = st.text_area(
            "Notes / lessons",
            value=s.get("feedback_notes") or "",
            key=f"notes_{s['strategy_id']}",
            height=80,
        )
        if (
            new_rating != rating
            or new_status != status
            or (new_notes != (s.get("feedback_notes") or ""))
        ):
            if st.button("Save feedback", key=f"savefb_{s['strategy_id']}"):
                sdb.set_feedback(
                    s["strategy_id"],
                    rating=new_rating, status=new_status, notes=new_notes,
                )
                st.success("Saved.")
                st.rerun()

        st.divider()
        st.markdown("**Record a result**")
        with st.form(f"add_result_{s['strategy_id']}", clear_on_submit=True):
            metric_options = list(METRIC_VOCAB.get(competition, ()))
            metric = st.selectbox(
                "Metric",
                options=metric_options + ["(custom)"],
                index=0 if metric_options else 0,
                key=f"metric_pick_{s['strategy_id']}",
            )
            if metric == "(custom)":
                metric = st.text_input(
                    "Custom metric name",
                    key=f"metric_custom_{s['strategy_id']}",
                )
            value = st.number_input(
                "Value",
                value=0.0, step=0.01, format="%.4f",
                key=f"value_{s['strategy_id']}",
            )
            note = st.text_input(
                "Note (optional)", key=f"resultnote_{s['strategy_id']}"
            )
            submit = st.form_submit_button("Add result")
            if submit:
                if not metric:
                    st.error("metric name required.")
                else:
                    sdb.add_result(
                        s["strategy_id"], metric, value=float(value), notes=note,
                    )
                    st.success(f"{metric} = {value} recorded.")
                    st.rerun()

        history = sdb.list_results(s["strategy_id"])
        if history:
            st.markdown("**Result history**")
            for h in history[:25]:
                v = h["value"]
                shown = f"{v:.4f}" if isinstance(v, (int, float)) else (h["text_value"] or "")
                st.markdown(
                    f"- `{h['metric']}` = **{shown}**"
                    + (f" · {h['notes']}" if h.get("notes") else "")
                )

        if st.button("🗑 Delete strategy", key=f"del_{s['strategy_id']}"):
            sdb.delete_strategy(s["strategy_id"])
            st.warning(f"Deleted {s['name']}.")
            st.rerun()


def _render_tab(competition: str) -> None:
    strategies = sdb.list_strategies(competition)
    st.markdown(
        f"### {LABELS[competition]} · {len(strategies)} saved strateg"
        f"{'y' if len(strategies) == 1 else 'ies'}"
    )

    col_q, col_min, col_status = st.columns([3, 2, 2])
    with col_q:
        query = st.text_input(
            "Filter (matches name, thesis, expression)",
            key=f"q_{competition}", placeholder="leave blank for all",
        )
    with col_min:
        min_rating = st.slider(
            "Min stars", 0, 5, 0, key=f"minr_{competition}",
        )
    with col_status:
        status_filter = st.multiselect(
            "Status", options=sdb.STATUS_VALUES, default=[],
            key=f"sf_{competition}",
        )

    filtered = []
    q_low = query.strip().lower()
    for s in strategies:
        if (s.get("rating") or 0) < min_rating:
            continue
        if status_filter and (s.get("status") or "draft") not in status_filter:
            continue
        if q_low:
            hay = f"{s['name']} {s.get('thesis','')} {s['expression']}".lower()
            if q_low not in hay:
                continue
        filtered.append(s)

    _render_add_strategy(competition)
    st.markdown("---")
    if not filtered:
        st.info("No strategies match the current filter.")
        return
    for s in filtered:
        _render_strategy_row(s, competition)


def main() -> None:
    st.set_page_config(
        page_title="StratEngine — saved strategies", page_icon="📈", layout="wide"
    )
    st.title("📈 StratEngine — saved strategies")
    st.caption(
        "Local SQLite store for every alpha you save. Rate 0–5 stars, "
        "track status, log results, edit lessons. Three competition tabs share "
        "the same model so cross-competition stats stay coherent."
    )

    with st.sidebar:
        st.subheader("Tools")
        if st.button("Import alpha_history.md"):
            n = sdb.import_alpha_history()
            st.success(f"Imported {n} BRAIN entries.")
        st.divider()
        for comp in COMPETITIONS:
            count = len(sdb.list_strategies(comp))
            st.markdown(f"**{LABELS[comp]}** · {count}")

    tabs = st.tabs([LABELS[c] for c in COMPETITIONS])
    for tab, comp in zip(tabs, COMPETITIONS):
        with tab:
            _render_tab(comp)


if __name__ == "__main__":
    main()
