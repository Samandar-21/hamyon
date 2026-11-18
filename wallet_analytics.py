import pandas as pd


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def get_dashboard_metrics(df):
    if df.empty:
        return {
            "total_income": 0.0,
            "total_expense": 0.0,
            "balance": 0.0,
            "month_income": 0.0,
            "month_expense": 0.0,
        }

    today = pd.Timestamp.today().normalize()
    start_month = today.replace(day=1)
    month_df = df[df["tx_date"] >= start_month.strftime("%Y-%m-%d")]

    total_income = float(df["income"].sum()) if "income" in df.columns else 0
    total_expense = float(df["expense"].sum()) if "expense" in df.columns else 0
    balance = total_income - total_expense

    month_income = float(month_df["income"].sum()) if not month_df.empty else 0
    month_expense = float(month_df["expense"].sum()) if not month_df.empty else 0

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": balance,
        "month_income": month_income,
        "month_expense": month_expense,
    }


def category_expenses(df):
    if df.empty:
        return pd.DataFrame(columns=["category", "expense"])
    exp_df = df[df["expense"] > 0].groupby("category", dropna=False)["expense"].sum().sort_values(ascending=False)
    return exp_df.rename_axis("category").reset_index(name="expense")


def monthly_summary(df):
    if df.empty:
        return pd.DataFrame(columns=["month", "income", "expense", "balance"])

    df = df.copy()
    df["month"] = pd.to_datetime(df["tx_date"]).dt.to_period("M").astype(str)
    grouped = df.groupby("month", as_index=False).agg(
        income=("income", "sum"),
        expense=("expense", "sum"),
    )
    grouped["balance"] = grouped["income"] - grouped["expense"]
    return grouped.sort_values("month")


def budget_status(df, budgets_df):
    if budgets_df.empty:
        return pd.DataFrame(columns=["category", "limit", "spent", "remaining"])

    expenses_by_cat = category_expenses(df)
    merged = budgets_df[["category", "limit_amount"]].rename(columns={"limit_amount": "limit"}).copy()
    merged = merged.merge(expenses_by_cat.rename(columns={"expense": "spent"}), on="category", how="left")
    merged["spent"] = merged["spent"].fillna(0)
    merged["remaining"] = merged["limit"] - merged["spent"]
    return merged[["category", "limit", "spent", "remaining"]].sort_values("spent", ascending=False)


def build_daily_digest(df, target_date=None):
    from datetime import date
    if not target_date:
        target_date = date.today().isoformat()

    month_names = {
        1: "yanvar", 2: "fevral", 3: "mart", 4: "aprel", 5: "may", 6: "iyun",
        7: "iyul", 8: "avgust", 9: "sentabr", 10: "oktabr", 11: "noyabr", 12: "dekabr"
    }

    try:
        t_obj = pd.to_datetime(target_date)
        day_num = t_obj.day
        month_str = month_names.get(t_obj.month, "")
        header_date = f"{day_num}-{month_str}"
    except Exception:
        header_date = target_date

    if df.empty:
        return (
            f"📊 *{header_date} hisoboti*\n\n"
            "Bugun hech qanday xarajat yoki amal amalga oshirilmadi.\n"
            "💰 Joriy balans: 0 so‘m"
        )

    # Bugungi amallar
    today_df = df[df["tx_date"].astype(str).str.startswith(str(target_date))]
    today_expenses = today_df[today_df["expense"] > 0]
    total_expense = float(today_expenses["expense"].sum()) if not today_expenses.empty else 0.0
    total_income = float(today_df["income"].sum()) if not today_df.empty else 0.0
    tx_count = len(today_df)

    # Kategoriyalar bo'yicha tahlil
    cat_lines = []
    if total_expense > 0:
        cat_group = today_expenses.groupby("category")["expense"].sum().sort_values(ascending=False)
        cat_icons = {
            "Oziq-ovqat": "🍽", "Ovqat": "🍽", "Transport": "🚗", "Kofe": "☕️",
            "Xaridlar": "🛍", "Kommunal": "💧", "Sog‘liq": "❤️", "Ta’lim": "🎓",
            "Ko‘ngilochar": "🎮", "Obunalar": "🔄", "Boshqa": "💬"
        }
        for cat, amt in cat_group.items():
            pct = int(round((amt / total_expense) * 100))
            amt_k = f"{amt/1000:,.0f}k".replace(",", " ") if amt >= 1000 else f"{amt:,.0f}"
            icon = cat_icons.get(cat, "💬")
            cat_lines.append(f"{icon} {cat:<12} {amt_k:>8}   {pct}%")

    # Oylik prognoz hisoblash
    metrics = get_dashboard_metrics(df)
    now = pd.Timestamp.now()
    cur_day = max(now.day, 1)
    days_in_month = pd.Period(now.strftime("%Y-%m")).days_in_month
    month_exp = metrics.get("month_expense", 0.0)

    # O'rtacha kunlik xarajat va prognoz
    avg_daily = month_exp / cur_day if cur_day > 0 else total_expense
    monthly_forecast = avg_daily * days_in_month
    balance = metrics.get("balance", 0.0)
    
    forecast_text = ""
    if avg_daily > 0 and balance > 0:
        days_left = int(balance / avg_daily)
        forecast_text = (
            f"🌧 *Oylik prognoz:*\n"
            f"Kutilayotgan xarajat: ~{monthly_forecast:,.0f} so‘m\n"
            f"Kuniga ~{avg_daily/1000:,.0f}k bilan *{days_left} kunga* yetadi."
        )
    elif monthly_forecast > 0:
        forecast_text = (
            f"🌧 *Oylik prognoz:*\n"
            f"Kutilayotgan xarajat: ~{monthly_forecast:,.0f} so‘m"
        )

    # Matnni yig'ish
    lines = [
        f"📊 *{header_date} hisoboti*",
        f"Xarajat: *–{total_expense:,.0f} so‘m*" if total_expense > 0 else "Xarajat: *0 so‘m*",
        f"Kirim: *+{total_income:,.0f} so‘m*" if total_income > 0 else None,
        f"Amaliyotlar soni: *{tx_count}*",
    ]
    lines = [l for l in lines if l]

    if cat_lines:
        lines.append("\n📁 *Qayerga ketdi:*")
        lines.append("```")
        lines.extend(cat_lines)
        lines.append("```")

    if forecast_text:
        lines.append(f"\n{forecast_text}")

    return "\n".join(lines)
