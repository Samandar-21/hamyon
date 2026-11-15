import pandas as pd
import streamlit as st
from datetime import date, timedelta
import hashlib
import hmac
import os

from wallet_analytics import budget_status, category_expenses, get_dashboard_metrics, monthly_summary
from wallet_db import add_transaction, db, delete_all_transactions, load_budgets, load_data, save_budget
from wallet_import import import_dataframe, read_uploaded_file
from wallet_utils import CATEGORIES, categorize_description

st.set_page_config(page_title="Smart Wallet — Aqlli Hamyon", page_icon="◈", layout="wide")

conn = db()

st.markdown(
    """
    <style>
    :root {
        --wallet-teal: #087c6d;
        --wallet-dark: #102c37;
        --wallet-bg: #f4f7fa;
        --wallet-muted: #788994;
    }
    [data-testid="stAppViewContainer"] {background: var(--wallet-bg);}
    [data-testid="stHeader"] {background: transparent;}
    .block-container {padding-top: 7rem; max-width: 1250px;}
    .st-key-wallet-topbar {
        position: fixed; top: 0; left: 0; width: 100vw; z-index: 9999;
        box-sizing: border-box;
        background: var(--wallet-bg);
        padding: 12px max(1.25rem, calc((100vw - 1250px) / 2)) 8px;
        border-bottom: 1px solid #e1e9eb;
        box-shadow: 0 8px 14px #18353e12;
    }
    .wallet-brand {font-size: 22px; font-weight: 750; color: #102c37; white-space: nowrap;}
    .st-key-wallet-topbar [data-testid="stHorizontalBlock"] {align-items: center;}
    div[role="radiogroup"] {gap: 8px; flex-wrap: wrap;}
    div[role="radiogroup"] label {
        border: 1px solid #dce6e9; border-radius: 10px; padding: 8px 13px;
        background: white; transition: background .15s ease;
    }
    div[role="radiogroup"] label:has(input:checked) {
        background: #d9f2e9; border-color: #9dd7c7; color: #087c6d;
    }
    h1, h2, h3 {color: #172b36;}
    [data-testid="stMetric"] {
        background: white; border: 1px solid #e8eef0; border-radius: 16px;
        padding: 18px 20px; box-shadow: 0 4px 16px #18353e08;
    }
    [data-testid="stMetricLabel"] {color: var(--wallet-muted);}
    [data-testid="stMetricValue"] {color: #172b36; font-size: 1.65rem;}
    [data-testid="stBaseButton-primary"] {
        background: var(--wallet-teal); border-color: var(--wallet-teal); color: white;
        border-radius: 10px; font-weight: 650;
    }
    [data-testid="stBaseButton-secondary"] {border-radius: 10px;}
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: white; border-color: #e8eef0; border-radius: 16px;
        box-shadow: 0 4px 16px #18353e08;
    }
    [data-testid="stForm"] {
        border: 0; padding: 0; background: transparent;
    }
    [data-testid="stDataFrame"] {border-radius: 12px; overflow: hidden;}
    .wallet-note {color: #788994; font-size: 12px;}
    @media (max-width: 700px) {
        .block-container {padding: 6.6rem .75rem 1.5rem !important;}
        .st-key-wallet-topbar {
            padding: 8px .65rem 5px;
            overflow: hidden;
        }
        .st-key-wallet-topbar [data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap;
            gap: .45rem;
        }
        .st-key-wallet-topbar [data-testid="column"]:first-child {
            flex: 0 0 102px !important;
            min-width: 0 !important;
        }
        .st-key-wallet-topbar [data-testid="column"]:last-child {
            flex: 1 1 0% !important;
            min-width: 0 !important;
        }
        .wallet-brand {font-size: 16px; white-space: normal; line-height: 1.15;}
        .st-key-wallet-topbar [data-testid="stCaptionContainer"] {display: none;}
        .st-key-wallet-topbar div[role="radiogroup"] {
            flex-wrap: nowrap;
            gap: 5px;
            overflow-x: auto;
            scrollbar-width: none;
        }
        .st-key-wallet-topbar div[role="radiogroup"]::-webkit-scrollbar {display: none;}
        .st-key-wallet-topbar div[role="radiogroup"] label {
            flex: 0 0 auto;
            padding: 6px 8px;
            font-size: 11px;
            white-space: nowrap;
        }
        [data-testid="stMetric"] {padding: 13px 15px; border-radius: 13px;}
        [data-testid="stMetricValue"] {font-size: 1.25rem;}
        h1 {font-size: 1.65rem !important;}
        h2 {font-size: 1.35rem !important;}
        h3 {font-size: 1.1rem !important;}
        [data-testid="stDataFrame"] {overflow-x: auto;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

access_password = os.environ.get("SMART_WALLET_ACCESS_PASSWORD", "")
webapp_url = os.environ.get("TELEGRAM_WEBAPP_URL", "").strip()
if webapp_url and not access_password:
    st.error("Telegram Web App uchun SMART_WALLET_ACCESS_PASSWORD ni ham o‘rnating.")
    st.stop()
if access_password:
    if not st.session_state.get("wallet_authenticated"):
        st.title("Smart Wallet")
        st.caption("Davom etish uchun kirish PIN/parolini kiriting.")
        with st.form("wallet_access_form"):
            entered_password = st.text_input("Kirish PIN/paroli", type="password")
            login_submitted = st.form_submit_button("Kirish", type="primary")
        if login_submitted:
            if hmac.compare_digest(entered_password, access_password):
                st.session_state.wallet_authenticated = True
                st.rerun()
            st.error("PIN/parol noto‘g‘ri.")
        st.stop()

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

with st.container(key="wallet-topbar"):
    top_brand, top_navigation = st.columns([1.1, 4], vertical_alignment="center")
    with top_brand:
        st.markdown('<div class="wallet-brand">◈ Smart Wallet</div>', unsafe_allow_html=True)
        st.caption("SHAXSIY MOLIYA")
    with top_navigation:
        pages = ["Dashboard", "Tranzaksiyalar", "Excel import", "Byudjetlar", "Operatsiya qo‘shish"]
        page = st.radio(
            "Bo‘lim",
            pages,
            index=pages.index(st.session_state.page),
            horizontal=True,
            label_visibility="collapsed",
        )
st.session_state.page = page
st.divider()


def money(value):
    return f"{value:,.0f} so‘m"


def period_range(period):
    today = date.today()
    if period == "Bugun":
        return today, today
    if period == "7 kun":
        return today - timedelta(days=6), today
    if period == "30 kun":
        return today - timedelta(days=29), today
    return None, None


def period_data(df, period):
    start, end = period_range(period)
    if start is None:
        return df
    return df[(df["tx_date"] >= start.isoformat()) & (df["tx_date"] <= end.isoformat())]


def render_dashboard(df):
    heading, action = st.columns([4, 1])
    with heading:
        st.title("Moliyaviy dashboard")
        st.caption("Kirim va chiqimlaringizni bir joyda boshqaring")
    with action:
        if st.button("＋ Operatsiya qo‘shish", type="primary", use_container_width=True):
            st.session_state.page = "Operatsiya qo‘shish"
            st.rerun()

    period = st.radio(
        "Hisobot davri",
        ["Bugun", "7 kun", "30 kun", "Barchasi"],
        index=2,
        horizontal=True,
        label_visibility="collapsed",
        key="dashboard_period",
    )
    selected = period_data(df, period)
    metrics = get_dashboard_metrics(df)
    selected_metrics = get_dashboard_metrics(selected)

    balance_col, income_col, expense_col = st.columns([1.15, 1, 1])
    with balance_col:
        st.markdown(
            f"""
            <div style="background:linear-gradient(110deg,#0f695d,#0b9883);color:white;
            border-radius:16px;padding:20px 22px;min-height:145px;box-shadow:0 4px 16px #18353e10">
              <div style="font-size:14px;color:#d5eee7">Jami balans (barcha vaqt)</div>
              <div style="font-size:30px;font-weight:700;margin:12px 0">{money(metrics['balance'])}</div>
              <div style="font-size:12px;color:#d5eee7">Barcha kirim − barcha chiqim</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with income_col:
        st.metric(f"{period} kirimi", money(selected_metrics["total_income"]))
    with expense_col:
        st.metric(f"{period} chiqimi", money(selected_metrics["total_expense"]))

    st.markdown("")
    chart_col, categories_col = st.columns([1.15, 0.85])
    with chart_col:
        with st.container(border=True):
            st.subheader("Xarajatlar dinamikasi")
            st.caption("Tanlangan davr bo‘yicha chiqimlar")
            if selected.empty:
                st.markdown('<div class="wallet-note">Bu davrda operatsiyalar yo‘q.</div>', unsafe_allow_html=True)
            elif period == "Barchasi":
                trend = monthly_summary(selected)
                st.bar_chart(trend.set_index("month")[["expense"]], color="#0b9883")
            else:
                daily = selected.copy()
                daily["date"] = pd.to_datetime(daily["tx_date"], errors="coerce")
                daily = daily.dropna(subset=["date"]).groupby("date", as_index=False)["expense"].sum()
                if not daily.empty:
                    st.bar_chart(daily.set_index("date")["expense"], color="#0b9883")
    with categories_col:
        with st.container(border=True):
            st.subheader("Xarajatlar kategoriyasi")
            categories = category_expenses(selected)
            if categories.empty:
                st.markdown('<div class="wallet-note">Xarajatlar yo‘q.</div>', unsafe_allow_html=True)
            else:
                total = categories["expense"].sum()
                for _, item in categories.head(7).iterrows():
                    amount = float(item["expense"])
                    share = amount / total if total else 0
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;gap:8px;margin:12px 0 4px'>"
                        f"<span>{item['category'] or 'Boshqa'}</span><b>{money(amount)}</b></div>"
                        f"<div style='background:#edf2f3;border-radius:20px;height:8px;overflow:hidden'>"
                        f"<div style='width:{share * 100:.1f}%;height:100%;background:#13a78f;border-radius:20px'></div></div>",
                        unsafe_allow_html=True,
                    )

    with st.container(border=True):
        st.subheader("Operatsiyalar tarixi")
        if df.empty:
            st.info("Hozircha operatsiyalar yo‘q. Yangi operatsiya qo‘shing yoki bank ko‘chirmasini import qiling.")
        else:
            st.dataframe(
                df[["tx_date", "description", "category", "income", "expense"]].head(10).rename(
                    columns={
                        "tx_date": "Sana",
                        "description": "Izoh",
                        "category": "Kategoriya",
                        "income": "Kirim",
                        "expense": "Chiqim",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
    st.caption("Maxfiylik: ma’lumotlar mahalliy SQLite bazasida saqlanadi.")


def render_import():
    st.title("Bank ko‘chirmasini import qilish")
    st.caption("Faylni yuklang, so‘ng saralash tugmasini bosing — ustunlar va kirim/chiqim turi avtomatik aniqlanadi.")
    uploaded = st.file_uploader("Faylni tanlang", type=["xlsx", "xls", "csv"])
    if not uploaded:
        st.info("Importdan oldin bank faylidagi shaxsiy ma’lumotlarni tekshiring.")
        return

    file_digest = hashlib.sha256(uploaded.getvalue()).hexdigest()
    st.success(f"Fayl yuklandi: {uploaded.name}")
    if st.button("Faylni o‘qish va saralash", type="primary"):
        try:
            uploaded.seek(0)
            raw = read_uploaded_file(uploaded)
            if raw.empty:
                st.warning("Faylda ma’lumot topilmadi.")
                return
            result = import_dataframe(conn, raw, uploaded.name)
            st.session_state["last_import"] = {
                "digest": file_digest,
                "result": result,
                "preview": raw.head(8),
                "error": None,
            }
        except Exception as exc:
            st.session_state["last_import"] = {
                "digest": file_digest,
                "result": None,
                "preview": None,
                "error": str(exc),
            }

    import_state = st.session_state.get("last_import")
    if not import_state or import_state["digest"] != file_digest:
        st.info("Fayl tayyor. Ma’lumotlarni o‘qib, tranzaksiyalarni kiritish uchun saralash tugmasini bosing.")
        return
    if import_state["error"]:
        st.error(f"Faylni saralashda xatolik: {import_state['error']}")
        return

    result = import_state["result"]
    detected = result["detected"]
    detected_labels = {
        "date_col": "Sana",
        "desc_col": "Izoh",
        "income_col": "Kirim",
        "expense_col": "Chiqim",
        "amount_col": "Summa",
        "type_col": "Tranzaksiya turi",
        "category_col": "Kategoriya",
        "status_col": "Holat",
    }
    found = [f"{label}: {detected[key]}" for key, label in detected_labels.items() if detected.get(key) is not None]
    st.success(
        f"Saralash yakunlandi. Qo‘shildi: {result['imported']} • "
        f"Takroriy: {result['duplicates']} • O‘tkazib yuborildi: {result['skipped']}"
    )
    if found:
        st.caption("Avtomatik aniqlangan ustunlar: " + " · ".join(found))
    st.dataframe(import_state["preview"], use_container_width=True)


def render_transactions(df):
    st.title("Operatsiyalar tarixi")
    if df.empty:
        st.info("Hozircha tranzaksiyalar yo‘q.")
        return
    with st.container(border=True):
        f1, f2, f3 = st.columns([1, 1, 1.4])
        with f1:
            start = st.date_input("Boshlanish sanasi", value=date.today() - timedelta(days=30))
        with f2:
            end = st.date_input("Tugash sanasi", value=date.today())
        with f3:
            search = st.text_input("Izoh bo‘yicha qidirish")
        category_filter = st.selectbox("Kategoriya", ["Hammasi"] + sorted(df["category"].dropna().unique().tolist()))
        view = df[(df["tx_date"] >= start.isoformat()) & (df["tx_date"] <= end.isoformat())]
        if search:
            view = view[view["description"].astype(str).str.contains(search, case=False, na=False, regex=False)]
        if category_filter != "Hammasi":
            view = view[view["category"] == category_filter]
        st.dataframe(
            view[["tx_date", "description", "category", "income", "expense", "source"]].rename(
                columns={"tx_date": "Sana", "description": "Izoh", "category": "Kategoriya", "income": "Kirim", "expense": "Chiqim", "source": "Manba"}
            ),
            use_container_width=True,
            hide_index=True,
        )
        if st.button("Barcha tranzaksiyalarni o‘chirish", type="secondary"):
            st.session_state["confirm_delete"] = True
        if st.session_state.get("confirm_delete"):
            st.warning("Haqiqatan ham barcha tranzaksiyalar o‘chirilsinmi?")
            yes, no = st.columns(2)
            if yes.button("Ha, o‘chirish"):
                delete_all_transactions(conn)
                st.session_state["confirm_delete"] = False
                st.rerun()
            if no.button("Bekor qilish"):
                st.session_state["confirm_delete"] = False
                st.rerun()


def render_budgets(df):
    st.title("Byudjetlar")
    with st.container(border=True):
        st.subheader("Kategoriya uchun oylik limit")
        with st.form("budget_form"):
            category = st.selectbox("Kategoriya", CATEGORIES)
            limit_amount = st.number_input("Limit (so‘m)", min_value=0.0, step=10000.0)
            submitted = st.form_submit_button("Saqlash", type="primary")
            if submitted:
                save_budget(conn, category, limit_amount)
                st.success(f"{category} uchun byudjet saqlandi.")
                st.rerun()
    budgets = load_budgets(conn)
    if budgets.empty:
        st.info("Hozircha byudjetlar yo‘q.")
        return
    current_month = date.today().replace(day=1).isoformat()
    month_df = df[df["tx_date"] >= current_month] if not df.empty else df
    st.subheader("Joriy oy holati")
    status = budget_status(month_df, budgets)
    st.dataframe(
        status.rename(columns={"category": "Kategoriya", "limit": "Limit", "spent": "Sarflandi", "remaining": "Qoldiq"}),
        use_container_width=True,
        hide_index=True,
    )


def render_manual_form():
    st.title("Operatsiya qo‘shish")
    st.caption("Kirim yoki chiqimni kiriting — balans va hisobotlar avtomatik yangilanadi.")

    if "manual_operation_type" not in st.session_state:
        st.session_state.manual_operation_type = "Chiqim"
    operation = st.session_state.manual_operation_type

    expense_col, income_col = st.columns(2)
    if expense_col.button(
        "↘  Chiqim",
        type="primary" if operation == "Chiqim" else "secondary",
        use_container_width=True,
        key="select_expense",
    ):
        st.session_state.manual_operation_type = "Chiqim"
        st.rerun()
    if income_col.button(
        "↗  Kirim",
        type="primary" if operation == "Kirim" else "secondary",
        use_container_width=True,
        key="select_income",
    ):
        st.session_state.manual_operation_type = "Kirim"
        st.rerun()

    categories = (
        ["Oziq-ovqat", "Transport", "Uy", "Kommunal", "Xaridlar", "Sog‘liq", "Ta’lim", "Ko‘ngilochar", "Boshqa"]
        if operation == "Chiqim"
        else ["Ish haqi", "Biznes", "Sovg‘a", "Qo‘shimcha daromad", "Boshqa"]
    )

    form_col, info_col = st.columns([1.35, 0.85], gap="large")
    with form_col:
        with st.container(border=True):
            st.subheader("Yangi operatsiya")
            desc = st.text_input("Izoh", placeholder="Masalan: Tushlik, taksi yoki oylik")
            suggested = categorize_description(desc)
            if suggested in categories:
                st.caption(f"Tavsiya etilgan kategoriya: **{suggested}**")

            with st.form("transaction_form", clear_on_submit=True):
                amount = st.number_input(
                    "Summa (so‘m)",
                    min_value=0.0,
                    step=1000.0,
                    help="Operatsiya summasini so‘mda kiriting.",
                )
                category = st.selectbox(
                    "Kategoriya",
                    categories,
                    index=categories.index(suggested) if suggested in categories else 0,
                )
                d = st.date_input("Sana", value=date.today())
                submitted = st.form_submit_button(
                    "Saqlash",
                    type="primary",
                    use_container_width=True,
                )
                if submitted:
                    if amount <= 0:
                        st.error("Summani noldan katta kiriting.")
                    else:
                        income = amount if operation == "Kirim" else 0
                        expense = amount if operation == "Chiqim" else 0
                        if add_transaction(conn, d, desc, category, income, expense):
                            st.success("Operatsiya saqlandi.")
                            st.rerun()
                        else:
                            st.warning("Bu operatsiya avval kiritilgan bo‘lishi mumkin.")

    with info_col:
        with st.container(border=True):
            if operation == "Chiqim":
                st.markdown("### ↘ Chiqim")
                st.markdown("Xarid, xizmat yoki boshqa to‘lovlaringizni qayd qiling.")
                st.markdown(
                    "<div style='background:#fff1f0;color:#bf5148;border-radius:12px;padding:14px;margin-top:18px'>"
                    "<b>Maslahat</b><br><span style='font-size:13px'>Izoh yozsangiz, mos kategoriya avtomatik tavsiya qilinadi.</span></div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown("### ↗ Kirim")
                st.markdown("Ish haqi, biznes yoki boshqa daromadlaringizni qayd qiling.")
                st.markdown(
                    "<div style='background:#e8f3f0;color:#126b60;border-radius:12px;padding:14px;margin-top:18px'>"
                    "<b>Maslahat</b><br><span style='font-size:13px'>Daromad turiga mos kategoriya tanlab, balansni yangilab boring.</span></div>",
                    unsafe_allow_html=True,
                )
            st.divider()
            st.caption("Ma’lumotlar saqlangach, dashboard ko‘rsatkichlari darhol yangilanadi.")


df = load_data(conn)
if page == "Dashboard":
    render_dashboard(df)
elif page == "Excel import":
    render_import()
elif page == "Tranzaksiyalar":
    render_transactions(df)
elif page == "Byudjetlar":
    render_budgets(df)
else:
    render_manual_form()
