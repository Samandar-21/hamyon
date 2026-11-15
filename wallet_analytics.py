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
