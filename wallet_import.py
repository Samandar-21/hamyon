import re
import unicodedata

import pandas as pd

from wallet_db import add_transaction
from wallet_utils import CATEGORIES, categorize_description, norm, parse_amount


ALIASES = {
    "date_col": [
        "sana", "date", "дата", "kun", "data", "transaction date",
        "operation date", "value date", "posting date",
    ],
    "desc_col": [
        "izoh", "назначение", "описание", "comment", "description",
        "details", "контрагент", "маъно", "purpose", "memo", "merchant",
    ],
    "income_col": [
        "kirim", "приход", "credit", "kredit", "кредит", "income", "поступление",
        "зачисление", "зачисл", "пополнение", "входящий", "credit turnover", "credit amount",
    ],
    "expense_col": [
        "chiqim", "расход", "debit", "debet", "дебет", "expense", "списание",
        "списан", "оплата", "исходящий", "debit turnover", "debit amount",
    ],
    "amount_col": [
        "summa", "сумма", "amount", "operation amount", "transaction amount",
        "оборот", "total", "miqdor", "payment amount", "paid amount",
    ],
    "type_col": [
        "tranzaksiya turi", "operatsiya turi", "transaction type",
        "operation type", "тип операции", "тип транзакции", "направление",
        "tur", "type",
    ],
    "category_col": ["kategoriya", "категория", "category"],
    "status_col": ["status", "статус", "holat", "состояние"],
}

INCOME_WORDS = (
    "kirim", "daromad", "income", "credit", "кредит", "приход",
    "поступ", "зачисл", "внесение",
)
EXPENSE_WORDS = (
    "chiqim", "xarajat", "expense", "debit", "дебет", "расход",
    "списан", "оплат", "покуп", "снятие",
)
CANCELLED_WORDS = ("bekor", "отмен", "cancel", "failed", "rad et", "не выполн", "отказ")


def _normalize_header(value):
    text = norm(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-zа-яё0-9]", "", text)


def _find_column(columns, key):
    aliases = [_normalize_header(alias) for alias in ALIASES[key]]
    normalized = [_normalize_header(column) for column in columns]
    for alias in aliases:
        for column, header in zip(columns, normalized):
            if header == alias:
                return column
    for alias in aliases:
        if len(alias) < 4:
            continue
        for column, header in zip(columns, normalized):
            if alias in header:
                return column
    return None


def build_import_mapping(raw):
    columns = list(raw.columns)
    mapping = {key: _find_column(columns, key) for key in ALIASES}

    if mapping["income_col"] == mapping["expense_col"]:
        mapping["income_col"] = None
        mapping["expense_col"] = None

    if mapping["amount_col"] in (mapping["income_col"], mapping["expense_col"]):
        mapping["amount_col"] = None

    if mapping["date_col"] is None:
        mapping["date_col"] = _infer_date_column(raw, mapping)

    if mapping["income_col"] is None and mapping["expense_col"] is None and mapping["amount_col"] is None:
        inferred = _infer_amount_columns(raw, mapping)
        mapping.update(inferred)

    return mapping


def read_uploaded_file(uploaded):
    if uploaded.name.lower().endswith(".csv"):
        try:
            return pd.read_csv(uploaded, sep=None, engine="python", encoding="utf-8-sig")
        except UnicodeDecodeError:
            uploaded.seek(0)
            return pd.read_csv(uploaded, sep=None, engine="python", encoding="cp1251")
    return pd.read_excel(uploaded)


def _parse_date(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        if not 20000 <= value <= 80000:
            return None
        parsed = pd.to_datetime(value, unit="D", origin="1899-12-30", errors="coerce")
    else:
        parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    return None if pd.isna(parsed) else parsed.date().isoformat()


def _infer_date_column(raw, mapping):
    excluded = {
        mapping[key]
        for key in ("desc_col", "income_col", "expense_col", "amount_col", "type_col", "category_col", "status_col")
        if mapping.get(key) is not None
    }
    candidates = []
    for column in raw.columns:
        if column in excluded:
            continue
        values = raw[column].dropna().head(50)
        if values.empty:
            continue
        valid = sum(_parse_date(value) is not None for value in values)
        ratio = valid / len(values)
        if ratio >= 0.7:
            text_ratio = sum(not isinstance(value, (int, float)) for value in values) / len(values)
            candidates.append((ratio, text_ratio, column))
    return max(candidates, default=(0, 0, None))[2]


def _numeric_ratio(series):
    values = series.dropna().head(100)
    if values.empty:
        return 0
    valid = 0
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            valid += 1
        elif re.search(r"\d", str(value)) and parse_amount(value) != 0:
            valid += 1
    return valid / len(values)


def _infer_amount_columns(raw, mapping):
    excluded = {
        mapping[key]
        for key in ("date_col", "desc_col", "type_col", "category_col", "status_col")
        if mapping.get(key) is not None
    }
    ignored_header_terms = (
        "balance", "остаток", "qoldiq", "saldo", "account", "счет", "счёт",
        "карта", "card", "номер", "код", "инн", "телефон", "phone", "id",
    )
    amount_header_terms = (
        "amount", "sum", "сумм", "miqdor", "payment", "paid", "оборот",
        "debit", "debet", "дебет", "расход", "списан", "credit", "kredit",
        "кредит", "приход", "поступ", "kirim", "chiqim",
    )
    candidates = []
    for column in raw.columns:
        if column in excluded:
            continue
        header = _normalize_header(column)
        if any(_normalize_header(term) in header for term in ignored_header_terms):
            continue
        ratio = _numeric_ratio(raw[column])
        if ratio < 0.7:
            continue
        type_from_header = _transaction_type(column)
        if type_from_header:
            candidates.append((column, type_from_header, ratio, 2))
        else:
            named_amount = any(_normalize_header(term) in header for term in amount_header_terms)
            candidates.append((column, None, ratio, 1 if named_amount else 0))

    typed = [(column, tx_type) for column, tx_type, _, score in candidates if tx_type and score == 2]
    if typed:
        result = {}
        for column, tx_type in typed:
            key = "income_col" if tx_type == "income" else "expense_col"
            if result.get(key) is None:
                result[key] = column
        if len(result) == len(typed) or len(result) == 2:
            return {**result, "amount_col": None}

    named = [item for item in candidates if item[3] == 1]
    if named:
        best_score = max((item[2], item[3]) for item in named)
        best = [item for item in named if (item[2], item[3]) == best_score]
    else:
        best = [item for item in candidates if item[3] == 0]

    if len(best) == 1:
        return {"amount_col": best[0][0]}
    if len(candidates) == 1:
        return {"amount_col": candidates[0][0]}
    return {}


def _transaction_type(value):
    text = norm(value)
    if any(word in text for word in INCOME_WORDS):
        return "income"
    if any(word in text for word in EXPENSE_WORDS):
        return "expense"
    return None


def _category(value, description, transaction_type):
    if transaction_type == "income":
        matched = categorize_description(value)
        if matched != "Boshqa":
            return matched
        matched = categorize_description(description)
        return matched if matched in {"Ish haqi", "Biznes", "Sovg‘a", "Qo‘shimcha daromad"} else "Boshqa"

    for candidate in (value, description):
        matched = categorize_description(candidate)
        if matched != "Boshqa":
            return matched

    text = norm(value)
    if any(word in text for word in ("food", "grocery", "продукт", "еда", "кафе", "магазин")):
        return "Oziq-ovqat"
    if any(word in text for word in ("utility", "коммун", "электр", "газ", "сув")):
        return "Kommunal"
    if any(word in text for word in ("transfer", "перевод", "o'tkazma")):
        return "O‘tkazma"
    if value in CATEGORIES:
        return value
    return "Boshqa"


def import_dataframe(conn, raw, source_name):
    mapping = build_import_mapping(raw)
    if mapping["date_col"] is None:
        raise ValueError("Sana ustuni avtomatik topilmadi. Ustun nomida sana/date/дата bo‘lishi kerak.")
    if mapping["income_col"] is None and mapping["expense_col"] is None and mapping["amount_col"] is None:
        raise ValueError("Summa ustuni avtomatik topilmadi. Ustun nomida summa/amount/debit/credit bo‘lishi kerak.")

    result = {
        "imported": 0,
        "duplicates": 0,
        "skipped": 0,
        "detected": mapping,
    }

    for _, row in raw.iterrows():
        try:
            tx_date = _parse_date(row[mapping["date_col"]])
            if not tx_date:
                result["skipped"] += 1
                continue

            desc_col = mapping["desc_col"]
            description = "" if desc_col is None or pd.isna(row[desc_col]) else str(row[desc_col]).strip()
            status_col = mapping["status_col"]
            if status_col is not None and any(word in norm(row[status_col]) for word in CANCELLED_WORDS):
                result["skipped"] += 1
                continue

            category_col = mapping["category_col"]
            bank_category = "" if category_col is None or pd.isna(row[category_col]) else str(row[category_col]).strip()
            transactions = []

            if mapping["income_col"] is not None or mapping["expense_col"] is not None:
                if mapping["income_col"] is not None:
                    transactions.append(("income", abs(parse_amount(row[mapping["income_col"]]))))
                if mapping["expense_col"] is not None:
                    transactions.append(("expense", abs(parse_amount(row[mapping["expense_col"]]))))
            else:
                amount = parse_amount(row[mapping["amount_col"]])
                type_col = mapping["type_col"]
                tx_type = _transaction_type(row[type_col]) if type_col is not None else None
                if tx_type is None and amount:
                    tx_type = "expense" if amount < 0 else "income"
                if tx_type:
                    transactions.append((tx_type, abs(amount)))

            for tx_type, amount in transactions:
                if not amount:
                    continue
                category = _category(bank_category, description, tx_type)
                income = amount if tx_type == "income" else 0
                expense = amount if tx_type == "expense" else 0
                if add_transaction(conn, tx_date, description, category, income, expense, source_name):
                    result["imported"] += 1
                else:
                    result["duplicates"] += 1
            if not transactions or all(not amount for _, amount in transactions):
                result["skipped"] += 1
        except (TypeError, ValueError, OverflowError):
            result["skipped"] += 1

    return result
