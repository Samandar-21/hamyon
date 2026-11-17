import os
from datetime import date
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from wallet_analytics import budget_status, category_expenses, get_dashboard_metrics, monthly_summary
from wallet_db import (
    add_transaction,
    db,
    delete_transaction,
    delete_all_transactions,
    get_user,
    load_budgets,
    load_data,
    register_or_update_user,
    save_budget,
    update_transaction_category,
)
from wallet_import import import_dataframe, read_uploaded_file
from wallet_utils import CATEGORIES, categorize_description, parse_quick_entry

app = FastAPI(title="Smart Wallet API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TransactionCreate(BaseModel):
    amount: float
    type: str  # "income" or "expense"
    category: Optional[str] = "Boshqa"
    description: Optional[str] = ""
    tx_date: Optional[str] = None
    source: Optional[str] = "Mobile App"

class QuickEntryRequest(BaseModel):
    text: str

class BudgetSet(BaseModel):
    category: str
    limit_amount: float

class CategoryUpdate(BaseModel):
    category: str


class UserAuthRequest(BaseModel):
    telegram_id: str
    phone_number: Optional[str] = ""
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    username: Optional[str] = ""

@app.get("/api/users/{telegram_id}")
def api_get_user(telegram_id: str):
    conn = db()
    try:
        user = get_user(conn, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
        return {"success": True, "user": user}
    finally:
        conn.close()

@app.post("/api/users/register")
def api_register_user(req: UserAuthRequest):
    conn = db()
    try:
        register_or_update_user(
            conn,
            req.telegram_id,
            req.phone_number or "",
            req.first_name or "",
            req.last_name or "",
            req.username or "",
        )
        user = get_user(conn, req.telegram_id)
        return {"success": True, "user": user}
    finally:
        conn.close()

@app.post("/api/admin/reset-database")
def api_reset_database():
    conn = db()
    try:
        conn.execute("DELETE FROM transactions")
        conn.execute("DELETE FROM budgets")
        conn.execute("DELETE FROM users")
        conn.commit()
        return {"success": True, "message": "Barcha ma'lumotlar va foydalanuvchilar tozalandi"}
    finally:
        conn.close()

@app.get("/api/dashboard")
def api_dashboard(period: Optional[str] = "30 kun"):
    conn = db()
    try:
        from app import period_data
        raw_df = load_data(conn)
        filtered_df = period_data(raw_df, period)
        all_metrics = get_dashboard_metrics(raw_df)
        period_metrics = get_dashboard_metrics(filtered_df)
        cat_expenses = category_expenses(filtered_df).to_dict(orient="records")
        monthly = monthly_summary(filtered_df).to_dict(orient="records")
        recent_txs = raw_df.head(20).to_dict(orient="records")
        return {
            "all_metrics": all_metrics,
            "period_metrics": period_metrics,
            "category_expenses": cat_expenses,
            "monthly_summary": monthly,
            "recent_transactions": recent_txs,
            "categories": CATEGORIES,
        }
    finally:
        conn.close()


@app.get("/api/transactions")
def api_transactions(limit: int = 100):
    conn = db()
    try:
        df = load_data(conn).head(limit)
        return df.to_dict(orient="records")
    finally:
        conn.close()


@app.post("/api/transactions")
def api_add_transaction(tx: TransactionCreate):
    conn = db()
    try:
        tx_date = tx.tx_date or date.today().isoformat()
        income = tx.amount if tx.type == "income" else 0.0
        expense = tx.amount if tx.type == "expense" else 0.0
        tx_id = add_transaction(conn, tx_date, tx.description, tx.category, income, expense, tx.source)
        if not tx_id:
            raise HTTPException(status_code=400, detail="Takroriy operatsiya (avval kiritilgan)")
        return {"success": True, "id": tx_id}
    finally:
        conn.close()


@app.post("/api/quick-entry")
def api_quick_entry(req: QuickEntryRequest):
    parsed = parse_quick_entry(req.text)
    if not parsed or parsed["amount"] <= 0:
        raise HTTPException(status_code=400, detail="Format tushunarsiz. Masalan: 45000 tushlik")

    conn = db()
    try:
        income = parsed["amount"] if parsed["type"] == "income" else 0.0
        expense = parsed["amount"] if parsed["type"] == "expense" else 0.0
        tx_id = add_transaction(
            conn,
            date.today().isoformat(),
            parsed["description"],
            parsed["category"],
            income,
            expense,
            "Mobile Quick",
        )
        if not tx_id:
            raise HTTPException(status_code=400, detail="Takroriy operatsiya")
        return {"success": True, "id": tx_id, "parsed": parsed}
    finally:
        conn.close()


@app.delete("/api/transactions/{tx_id}")
def api_delete_transaction(tx_id: int):
    conn = db()
    try:
        delete_transaction(conn, tx_id)
        return {"success": True}
    finally:
        conn.close()


@app.patch("/api/transactions/{tx_id}/category")
def api_update_category(tx_id: int, req: CategoryUpdate):
    conn = db()
    try:
        update_transaction_category(conn, tx_id, req.category)
        return {"success": True}
    finally:
        conn.close()


@app.get("/api/budgets")
def api_get_budgets():
    conn = db()
    try:
        df = load_data(conn)
        budgets_df = load_budgets(conn)
        status = budget_status(df, budgets_df).to_dict(orient="records")
        return {"budgets": status}
    finally:
        conn.close()


@app.post("/api/budgets")
def api_save_budget(req: BudgetSet):
    conn = db()
    try:
        save_budget(conn, req.category, req.limit_amount)
        return {"success": True}
    finally:
        conn.close()


@app.post("/api/import-excel")
async def api_import_excel(file: UploadFile = File(...)):
    conn = db()
    try:
        raw = read_uploaded_file(file.file)
        if raw.empty:
            raise HTTPException(status_code=400, detail="Fayl bo‘sh yoki o‘qib bo‘lmadi")
        result = import_dataframe(conn, raw, file.filename)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.get("/api/reports")
def api_reports(period: str = "Oy"):
    conn = db()
    try:
        from app import period_data
        raw_df = load_data(conn)
        
        # Period mapping
        p_map = {"Oy": "30 kun", "Chorak": "Barchasi", "Yil": "Barchasi"}
        filtered = period_data(raw_df, p_map.get(period, "30 kun"))
        
        metrics = get_dashboard_metrics(filtered)
        cat_exp = category_expenses(filtered).to_dict(orient="records")
        monthly = monthly_summary(raw_df).to_dict(orient="records")
        
        return {
            "metrics": metrics,
            "category_expenses": cat_exp,
            "monthly_summary": monthly,
        }
    finally:
        conn.close()


# Mount static directory for Mobile PWA
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
