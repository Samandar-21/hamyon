import os
from datetime import date
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from wallet_analytics import (
    budget_status,
    build_daily_digest,
    category_expenses,
    get_dashboard_metrics,
    monthly_summary,
)
from wallet_db import (
    add_audit_log,
    add_transaction,
    db,
    delete_transaction,
    delete_all_transactions,
    get_admin_by_username,
    get_all_users,
    get_audit_logs,
    get_user,
    init_default_admin,
    load_budgets,
    load_data,
    register_or_update_user,
    save_budget,
    update_transaction_category,
    update_user_activity,
    update_user_status,
    verify_password,
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


# Admin Request Models
class AdminLoginRequest(BaseModel):
    username: str
    password: str

class UserStatusUpdateRequest(BaseModel):
    status: str  # "active" or "blocked"

# Simple Secure Token implementation
ADMIN_SECRET_KEY = os.environ.get("ADMIN_JWT_SECRET", "hamyon_super_secret_jwt_key_2026")

def create_admin_token(admin_dict: dict) -> str:
    import json, base64, hmac, hashlib, time
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload_data = {
        "sub": admin_dict["username"],
        "id": admin_dict["id"],
        "role": admin_dict["role"],
        "name": admin_dict["full_name"],
        "exp": int(time.time()) + (86400 * 7)  # 7 kunlik sessiya
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip("=")
    signature = hmac.new(ADMIN_SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    sig_str = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{header}.{payload}.{sig_str}"

def verify_admin_token(token: str) -> dict:
    import json, base64, hmac, hashlib, time
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="Noto‘g‘ri token formati")
        header, payload, sig = parts
        expected_sig = hmac.new(ADMIN_SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        expected_sig_str = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")
        if not hmac.compare_digest(sig, expected_sig_str):
            raise HTTPException(status_code=401, detail="Token haqiqiy emas")
        padding = "=" * (4 - len(payload) % 4)
        payload_data = json.loads(base64.urlsafe_b64decode(payload + padding).decode())
        if payload_data.get("exp", 0) < time.time():
            raise HTTPException(status_code=401, detail="Sessiya vaqti tugagan")
        return payload_data
    except Exception:
        raise HTTPException(status_code=401, detail="Avtorizatsiyadan o‘tilmagan")

from fastapi import Header

def get_current_admin(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Avtorizatsiya tokeni talab qilinadi")
    token = authorization.split("Bearer ", 1)[1].strip()
    return verify_admin_token(token)

@app.on_event("startup")
def on_startup():
    conn = db()
    try:
        init_default_admin(conn)
    finally:
        conn.close()

# ----------------- ADMIN API ENDPOINTS -----------------
@app.post("/api/admin/login")
def api_admin_login(req: AdminLoginRequest):
    conn = db()
    try:
        admin = get_admin_by_username(conn, req.username)
        if not admin or not verify_password(req.password, admin["password_hash"]):
            raise HTTPException(status_code=401, detail="Login yoki parol noto‘g‘ri!")
        if not admin["is_active"]:
            raise HTTPException(status_code=403, detail="Ushbu admin hisobi bloklangan!")
        
        token = create_admin_token(admin)
        add_audit_log(conn, admin["id"], admin["username"], "LOGIN", details="Admin tizimga kirdi")
        return {
            "success": True,
            "token": token,
            "admin": {
                "id": admin["id"],
                "username": admin["username"],
                "name": admin["full_name"],
                "role": admin["role"]
            }
        }
    finally:
        conn.close()

@app.get("/api/admin/me")
def api_admin_me(authorization: Optional[str] = Header(None)):
    admin_payload = get_current_admin(authorization)
    return {"success": True, "admin": admin_payload}

@app.get("/api/admin/dashboard-stats")
def api_admin_dashboard_stats(authorization: Optional[str] = Header(None)):
    admin = get_current_admin(authorization)
    conn = db()
    try:
        users = get_all_users(conn)
        tx_df = load_data(conn)
        today_str = date.today().isoformat()
        
        total_users = len(users)
        active_today_users = len([u for u in users if (u.get("last_active") or "").startswith(today_str)])
        new_today_users = len([u for u in users if (u.get("created_at") or "").startswith(today_str)])
        
        total_txs = len(tx_df)
        today_txs_df = tx_df[tx_df["tx_date"].astype(str).str.startswith(today_str)] if not tx_df.empty else tx_df
        today_txs_count = len(today_txs_df)
        
        total_income = float(tx_df["income"].sum()) if "income" in tx_df.columns else 0.0
        total_expense = float(tx_df["expense"].sum()) if "expense" in tx_df.columns else 0.0
        
        # Sources distribution
        sources_count = tx_df["source"].value_counts().to_dict() if not tx_df.empty and "source" in tx_df.columns else {}
        
        # Category breakdown
        cat_exp = category_expenses(tx_df).to_dict(orient="records") if not tx_df.empty else []
        monthly = monthly_summary(tx_df).to_dict(orient="records") if not tx_df.empty else []
        
        return {
            "stats": {
                "total_users": total_users,
                "active_today_users": max(active_today_users, 1 if total_users > 0 else 0),
                "new_today_users": new_today_users,
                "total_txs": total_txs,
                "today_txs": today_txs_count,
                "total_income": total_income,
                "total_expense": total_expense,
                "bot_status": "Online (Faol)",
                "miniapp_status": "Online (Vercel)"
            },
            "sources": sources_count,
            "category_expenses": cat_exp,
            "monthly_summary": monthly,
            "recent_transactions": tx_df.head(10).to_dict(orient="records") if not tx_df.empty else []
        }
    finally:
        conn.close()

@app.get("/api/admin/users")
def api_admin_get_users(
    authorization: Optional[str] = Header(None),
    search: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20
):
    admin = get_current_admin(authorization)
    conn = db()
    try:
        users = get_all_users(conn)
        tx_df = load_data(conn)
        
        # Count transactions per user by phone or matching description
        user_list = []
        for u in users:
            uid = str(u.get("telegram_id", ""))
            u_txs = 0
            if not tx_df.empty and "description" in tx_df.columns:
                # count
                pass
            u_data = dict(u)
            u_data["tx_count"] = 0
            user_list.append(u_data)
        
        if search:
            s = search.lower()
            user_list = [
                u for u in user_list
                if s in str(u.get("telegram_id", "")).lower()
                or s in str(u.get("first_name", "")).lower()
                or s in str(u.get("username", "")).lower()
                or s in str(u.get("phone_number", "")).lower()
            ]
        
        if status and status != "all":
            user_list = [u for u in user_list if u.get("status") == status]
            
        total_count = len(user_list)
        start_idx = (page - 1) * limit
        paginated = user_list[start_idx : start_idx + limit]
        
        return {
            "total": total_count,
            "page": page,
            "limit": limit,
            "users": paginated
        }
    finally:
        conn.close()

@app.patch("/api/admin/users/{telegram_id}/status")
def api_admin_change_user_status(
    telegram_id: str,
    req: UserStatusUpdateRequest,
    authorization: Optional[str] = Header(None)
):
    admin = get_current_admin(authorization)
    if admin.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Faqat Superadmin foydalanuvchini bloklashi yoki faollashtirishi mumkin!")
    
    conn = db()
    try:
        update_user_status(conn, telegram_id, req.status)
        add_audit_log(
            conn,
            admin["id"],
            admin["sub"],
            f"USER_STATUS_{req.status.upper()}",
            details=f"Telegram ID {telegram_id} holati {req.status} ga o‘zgartirildi"
        )
        return {"success": True, "status": req.status}
    finally:
        conn.close()

@app.get("/api/admin/audit-logs")
def api_admin_logs(authorization: Optional[str] = Header(None), limit: int = 50):
    admin = get_current_admin(authorization)
    conn = db()
    try:
        logs = get_audit_logs(conn, limit)
        return {"logs": logs}
    finally:
        conn.close()

@app.get("/api/admin/bot-health")
def api_admin_bot_health(authorization: Optional[str] = Header(None)):
    admin = get_current_admin(authorization)
    conn = db()
    try:
        tx_count = len(load_data(conn))
        user_count = len(get_all_users(conn))
        return {
            "status": "healthy",
            "bot_username": "@hamyon_hisobi_bot",
            "database_connected": True,
            "total_transactions": tx_count,
            "total_registered_users": user_count,
            "webhook": "Long Polling (Barqaror)",
            "api_server": "FastAPI uvicorn v0.54.0",
            "mini_app_url": "https://hamyon-tan.vercel.app"
        }
    finally:
        conn.close()

# --------------------------------------------------------

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

@app.get("/api/reports/daily-digest")
def api_daily_digest(target_date: Optional[str] = None):
    conn = db()
    try:
        df = load_data(conn)
        digest = build_daily_digest(df, target_date)
        return {"success": True, "digest": digest}
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


@app.post("/api/admin/reset-data")
def api_admin_reset_data(authorization: Optional[str] = Header(None)):
    admin = get_current_admin(authorization)
    conn = db()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM transactions")
        c.execute("DELETE FROM users")
        c.execute("DELETE FROM budgets")
        c.execute("DELETE FROM audit_logs")
        conn.commit()
        return {"success": True, "message": "Ma'lumotlar bazasi 0 holatga keltirildi."}
    finally:
        conn.close()


# Mount static directory for Mobile PWA
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
