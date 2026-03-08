"""
ai_advisor_module.py  — FinSuite Pro
=====================================
🔑 მთავარი გამოსწორებები:
  1. Circular loop მოხსნილია:
     - Hierarchy check: მხოლოდ ACTIVE კოდები (არა IGNORE)
     - Orphan check: მშობელი კოდები სრულად გამოირიცხება
  2. Orphan fix: თვითოეულ კოდს smart_suggest()-ით ინდივიდუალური
     კატეგორია ენიჭება — ედიტირებადი ცხრილით
  3. smart_suggest(): კოდის prefix + სახელის keywords მიხედვით
"""

import streamlit as st
import pandas as pd
import utils
import time

BS_CATS = [
    "BS: Current Assets (მიმდინარე აქტივები)",
    "BS: Non-Current Assets (გრძელვადიანი აქტივები)",
    "BS: Current Liabilities (მიმდინარე ვალდ.)",
    "BS: Non-Current Liabilities (გრძელვადიანი ვალდ.)",
    "BS: Equity (კაპიტალი)",
]
REVENUE_CATS = ["Revenue (შემოსავალი)"]
EXPENSE_CATS = [
    "COGS (თვითღირებულება)",
    "Operating Expenses (საოპერაციო ხარჯები)",
    "Depreciation (ცვეთა/ამორტიზაცია)",
    "Interest (საპროცენტო ხარჯი)",
    "Tax (მოგების გადასახადი)",
]
ALL_PL_CATS = REVENUE_CATS + EXPENSE_CATS + ["Other Income/Expense (სხვა არასაოპერაციო)"]
ALL_VALID_CATS = BS_CATS + ALL_PL_CATS
IGNORE_CAT = "IGNORE (იგნორირება)"


# ─────────────────────────────────────────────────────────────
# ჭკვიანი კატეგორიის გამოცნობა
# ─────────────────────────────────────────────────────────────
def smart_suggest(code: str, name: str = "") -> str:
    code = str(code).strip()
    name = str(name).lower()

    # მშობელი კოდები → IGNORE
    if len(code) >= 3 and (code.endswith("00") or code.endswith("000")):
        return IGNORE_CAT

    # სახელის საკვანძო სიტყვები
    if any(k in name for k in ["ცვეთა","ამორტ","depreci","amort"]):
        return "Depreciation (ცვეთა/ამორტიზაცია)"
    if any(k in name for k in ["საპროცენტო","პროცენტ","interest"]):
        return "Interest (საპროცენტო ხარჯი)"
    if any(k in name for k in ["გადასახად","income tax","profit tax"]):
        return "Tax (მოგების გადასახადი)"

    pfx2 = code[:2]
    pfx1 = code[:1]

    if pfx2 in ("11","12","13","14","15","16","17","18","19"):
        return "BS: Current Assets (მიმდინარე აქტივები)"
    if pfx2 in ("21","22","23","24","25","26","27","28","29"):
        return "BS: Non-Current Assets (გრძელვადიანი აქტივები)"
    if pfx2 in ("31","32","33","34","35","36","37","38","39"):
        return "BS: Current Liabilities (მიმდინარე ვალდ.)"
    if pfx2 in ("41","42","43","44","45","46","47","48","49"):
        return "BS: Non-Current Liabilities (გრძელვადიანი ვალდ.)"
    if pfx1 == "5":
        return "BS: Equity (კაპიტალი)"
    if pfx1 == "6":
        return "Revenue (შემოსავალი)"
    if pfx2 in ("71","72"):
        return "COGS (თვითღირებულება)"
    if pfx1 == "7":
        return "Operating Expenses (საოპერაციო ხარჯები)"
    if pfx2 == "81":
        return "Interest (საპროცენტო ხარჯი)"
    if pfx1 == "8":
        return "Other Income/Expense (სხვა არასაოპერაციო)"
    if pfx1 == "9":
        return "Tax (მოგების გადასახადი)"

    return IGNORE_CAT


def _find_parents(all_codes: set) -> set:
    parents = set()
    for p in all_codes:
        for c in all_codes:
            if p != c and c.startswith(p):
                parents.add(p)
                break
    return parents


# ─────────────────────────────────────────────────────────────
# DATA HEALTH CHECK — loop-free
# ─────────────────────────────────────────────────────────────
def check_data_health(df: pd.DataFrame, context: str = "all") -> list:
    if df.empty:
        return []

    df = df.copy()
    df["Code"] = df["Code"].astype(str).str.strip()
    if "Category" not in df.columns:
        df["Category"] = IGNORE_CAT

    issues = []
    all_codes = set(df["Code"])
    all_parents = _find_parents(all_codes)

    # 0. HIERARCHY CHECK — მხოლოდ active კოდები
    active_codes = set(df[df["Category"] != IGNORE_CAT]["Code"])
    bad_parents = []
    for p in active_codes:
        for c in active_codes:
            if p != c and c.startswith(p):
                bad_parents.append(p)
                break

    if bad_parents:
        bad_df = df[df["Code"].isin(bad_parents)]
        details = bad_df.apply(
            lambda x: f"⚠️ {x['Code']} ({x['Name']})  →  {x['Category']}", axis=1
        ).tolist()
        issues.append({
            "type": "hierarchy_issue",
            "title": "🔴 გაორმაგების რისკი (მშობელი კოდები)",
            "desc": f"{len(bad_parents)} მშობელი კოდი active კატეგ.-ით — შვილებიც სიაშია.",
            "details": details,
            "codes": bad_df["Code"].unique(),
            "context": context,
        })

    # 1. ORPHAN CHECK — მშობლები გამოირიცხება
    if context == "PL":
        scope = df[df["Code"].str.match(r"^[6789]", na=False)]
        orphans_df = scope[~scope["Category"].isin(ALL_PL_CATS) & (scope["Category"] != IGNORE_CAT)]
    elif context == "BS":
        scope = df[df["Code"].str.match(r"^[12345]", na=False)]
        orphans_df = scope[~scope["Category"].isin(BS_CATS) & (scope["Category"] != IGNORE_CAT)]
    else:
        orphans_df = df[~df["Category"].isin(ALL_VALID_CATS) & (df["Category"] != IGNORE_CAT)]

    real_orphans = orphans_df[~orphans_df["Code"].isin(all_parents)]

    if not real_orphans.empty:
        suggestions = {
            str(r["Code"]): smart_suggest(r["Code"], r.get("Name",""))
            for _, r in real_orphans.iterrows()
        }
        details = real_orphans.apply(
            lambda x: f"🔴 {x['Code']} - {x['Name']}  →  [{suggestions.get(str(x['Code']), IGNORE_CAT)}]",
            axis=1,
        ).tolist()
        issues.append({
            "type": "orphan",
            "title": "🔴 გაუმართავი მეპინგი (Orphans)",
            "desc": "კოდები გაუმართავი კატეგორიით. AI წინადადება ნახეთ ↓",
            "details": details,
            "codes": real_orphans["Code"].unique(),
            "suggestions": suggestions,
            "context": context,
        })

    # 2. SIGN ANOMALIES
    if context in ("BS","all"):
        cash_neg = df[
            df["Code"].str.match(r"^1[12]", na=False)
            & df["Category"].str.contains("Current Assets", na=False)
            & (df["Net"] < -1)
        ]
        if not cash_neg.empty:
            issues.append({
                "type": "cash_negative",
                "title": "⚠️ უარყოფითი ფული/ბანკი",
                "desc": "ოვერდრაფტი? ვალდებულება?",
                "details": cash_neg.apply(lambda x: f"📉 {x['Code']}: {x['Net']:,.2f}", axis=1).tolist(),
                "codes": cash_neg["Code"].unique(),
                "context": "BS",
            })

    if context in ("PL","all"):
        rev_pos = df[df["Category"].isin(REVENUE_CATS) & (df["Net"] > 1)]
        if not rev_pos.empty:
            issues.append({
                "type": "revenue_positive",
                "title": "⚠️ შემოსავალი დებეტშია",
                "desc": "ხარჯი ხომ არაა?",
                "details": rev_pos.apply(lambda x: f"📈 {x['Code']}: {x['Net']:,.2f}", axis=1).tolist(),
                "codes": rev_pos["Code"].unique(),
                "context": "PL",
            })
        exp_neg = df[df["Category"].isin(EXPENSE_CATS) & (df["Net"] < -1)]
        if not exp_neg.empty:
            issues.append({
                "type": "expense_negative",
                "title": "⚠️ ხარჯი კრედიტშია",
                "desc": "შემოსავალი ხომ არაა?",
                "details": exp_neg.apply(lambda x: f"📉 {x['Code']}: {x['Net']:,.2f}", axis=1).tolist(),
                "codes": exp_neg["Code"].unique(),
                "context": "PL",
            })

    return issues


# ─────────────────────────────────────────────────────────────
# FIX LOGIC
# ─────────────────────────────────────────────────────────────
def apply_fix_logic(issue_codes, target_category, source_key=None):
    issue_codes = [str(c).strip() for c in issue_codes]
    updated = False

    def _apply(df_ref):
        df_ref["Code"] = df_ref["Code"].astype(str).str.strip()
        for code in issue_codes:
            mask = df_ref["Code"] == code
            if not mask.any():
                continue
            cat = target_category.get(code, IGNORE_CAT) if isinstance(target_category, dict) else target_category
            df_ref.loc[mask, "Category"] = cat
        return df_ref

    if st.session_state.df_working is not None:
        st.session_state.df_working = _apply(st.session_state.df_working)
        updated = True

    if source_key:
        db = utils.load_db()
        if source_key in db:
            df_temp = _apply(pd.DataFrame(db[source_key]))
            utils.save_to_db(source_key, df_temp.to_dict("records"))
            updated = True

    if updated:
        st.cache_data.clear()
        st.toast("✅ შესწორებულია!", icon="✅")
        time.sleep(0.8)
        st.rerun()
    else:
        st.error("ვერ მოხერხდა შესწორება.")


# ─────────────────────────────────────────────────────────────
# DIALOG
# ─────────────────────────────────────────────────────────────
@st.dialog("🤖 AI ფინანსური ასისტენტი")
def audit_dialog(issue: dict, source_key=None):
    st.markdown(f"### {issue['title']}")
    st.caption(issue.get("desc",""))
    st.markdown("---")

    if issue["type"] == "hierarchy_issue":
        st.warning(
            "ეს კოდები **მშობლები** არიან — მათი შვილებიც active კატეგ.-ით არიან.\n\n"
            "გამოსავალი: მშობელ კოდებს IGNORE მივანიჭოთ (შვილები ჯამდება)."
        )
        for det in issue["details"][:8]:
            st.code(det, language="text")
        if st.button("✅ მშობლებს IGNORE", type="primary", key="fix_hier"):
            apply_fix_logic(issue["codes"], IGNORE_CAT, source_key)

    elif issue["type"] == "orphan":
        suggestions: dict = issue.get("suggestions", {})
        st.info("💡 AI-მ გამოიცნო კატეგორია. შეგიძლიათ შეცვალოთ სანამ გამოიყენებთ.")

        rows = []
        df_w = st.session_state.df_working
        for code in issue["codes"]:
            name, net = "", 0.0
            if df_w is not None:
                _tmp = df_w[df_w["Code"].astype(str).str.strip() == str(code)]
                if not _tmp.empty:
                    name = _tmp.iloc[0].get("Name","")
                    net  = _tmp.iloc[0].get("Net", 0.0)
            rows.append({
                "Code": str(code),
                "Name": name,
                "Net": net,
                "კატეგორია": suggestions.get(str(code), IGNORE_CAT),
            })

        edited = st.data_editor(
            pd.DataFrame(rows),
            column_config={
                "კატეგორია": st.column_config.SelectboxColumn(
                    "კატეგორია", options=utils.MAPPING_OPTIONS, required=True, width="large"),
                "Code": st.column_config.TextColumn("კოდი", width="small"),
                "Name": st.column_config.TextColumn("სახელი", width="medium"),
                "Net":  st.column_config.NumberColumn("Net", format="%.2f", width="small"),
            },
            use_container_width=True,
            hide_index=True,
            key="orphan_fix_editor",
        )

        final_map = dict(zip(edited["Code"].astype(str), edited["კატეგორია"]))
        if st.button("✅ გამოყენება", type="primary", key="fix_orphan"):
            apply_fix_logic(issue["codes"], final_map, source_key)

    elif issue["type"] == "revenue_positive":
        for det in issue["details"][:6]: st.code(det, language="text")
        st.info("💡 გადავიტანოთ **'საოპერაციო ხარჯებში'**?")
        c1, c2 = st.columns(2)
        if c1.button("✅ გადატანა", type="primary", key="fix_rev"):
            apply_fix_logic(issue["codes"], "Operating Expenses (საოპერაციო ხარჯები)", source_key)
        if c2.button("❌ გაუქმება", key="cancel_rev"): st.rerun()

    elif issue["type"] == "expense_negative":
        for det in issue["details"][:6]: st.code(det, language="text")
        st.info("💡 გადავიტანოთ **'სხვა შემოსავალში'**?")
        if st.button("✅ გადატანა", type="primary", key="fix_exp"):
            apply_fix_logic(issue["codes"], "Other Income/Expense (სხვა არასაოპერაციო)", source_key)

    elif issue["type"] == "cash_negative":
        for det in issue["details"][:6]: st.code(det, language="text")
        st.info("💡 გადავიტანოთ **'მიმდინარე ვალდებულებებში'**?")
        if st.button("✅ გადატანა", type="primary", key="fix_cash"):
            apply_fix_logic(issue["codes"], "BS: Current Liabilities (მიმდინარე ვალდ.)", source_key)

    st.markdown("---")
    if st.button("დახურვა", key="close_dialog"): st.rerun()


# ─────────────────────────────────────────────────────────────
# RENDER UI
# ─────────────────────────────────────────────────────────────
def render_audit_ui(df: pd.DataFrame, context: str, source_key=None, ui_key: str = "default"):
    issues = check_data_health(df, context)
    problematic_codes: set = set()

    if not issues:
        st.success(f"✅ {context} მონაცემები სუფთაა.")
        return problematic_codes

    with st.expander(f"🚨 AI აუდიტი — {len(issues)} შენიშვნა", expanded=True):
        for i, issue in enumerate(issues):
            if "codes" in issue:
                problematic_codes.update(str(c) for c in issue["codes"])
            c1, c2 = st.columns([5, 1])
            c1.warning(f"**{issue['title']}** — {issue.get('desc','')[:90]}")
            if c2.button("🔍 გამოსწორება", key=f"ai_btn_{context}_{ui_key}_{issue['type']}_{i}"):
                audit_dialog(issue, source_key)

    return problematic_codes


def render_strategy_btn(kpis):
    pass