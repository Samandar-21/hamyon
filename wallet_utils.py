import hashlib
import re
from typing import Iterable, Optional

import pandas as pd

CATEGORIES = [
    "Oziq-ovqat",
    "Transport",
    "Uy",
    "Kommunal",
    "Uy-joy / Kommunal",
    "Aloqa",
    "Kiyim-kechak",
    "Xaridlar",
    "Sog‘liq",
    "Ta’lim",
    "Ko‘ngilochar",
    "Ish haqi",
    "Biznes",
    "Sovg‘a",
    "Qo‘shimcha daromad",
    "O‘tkazma",
    "Boshqa",
]


def norm(s):
    return str(s).strip().lower().replace("ё", "е")


def fingerprint(d, desc, inc, exp):
    raw = f"{d}|{str(desc).strip().lower()}|{round(float(inc), 2)}|{round(float(exp), 2)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def guess_col(columns, words):
    for c in columns:
        nc = norm(c)
        if any(w in nc for w in words):
            return c
    return None


def parse_amount(x):
    if pd.isna(x):
        return 0.0

    s = str(x).strip()
    if s == "" or s.lower() in {"nan", "none", "null"}:
        return 0.0

    s = s.replace("\xa0", "").replace(" ", "")
    s = s.replace("so'm", "").replace("som", "").replace("сум", "")
    s = s.replace("₽", "").replace("$", "").replace("USD", "").replace("EUR", "")
    s = s.replace("€", "")

    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]

    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) > 1 and len(parts[-1]) <= 2:
            s = ".".join(parts)
        else:
            s = "".join(parts)

    s = "".join(ch for ch in s if ch.isdigit() or ch in ".-")
    if s in ("", "-", "."):
        return 0.0

    try:
        return float(s)
    except ValueError:
        return 0.0


def categorize_description(description, transaction_type="expense"):
    text = str(description or "").lower()

    if transaction_type == "income" or any(w in text for w in ["oylik", "maosh", "salary", "stipendiya", "зарплат", "аванс", "стипенд"]):
        if any(w in text for w in ["maosh", "ish haqi", "salary", "зарплат", "аванс", "oylik", "stipendiya", "стипенд"]):
            return "Ish haqi"
        if any(w in text for w in ["biznes", "business", "savdo", "klient", "mijoz", "kassir"]):
            return "Biznes"
        if any(w in text for w in ["sovg‘a", "sovga", "gift", "hadya"]):
            return "Sovg‘a"
        if any(w in text for w in ["qo‘shimcha", "qoshimcha", "bonus", "keshbek", "cashback", "extra income"]):
            return "Qo‘shimcha daromad"
        if any(w in text for w in ["transfer", "перевод", "o'tkazma", "otkazma", "perevod", "pul tashladim"]):
            return "O‘tkazma"
        if transaction_type == "income":
            return "Boshqa"

    # Transport
    if any(w in text for w in [
        "taxi", "taksi", "автобус", "такси", "avtobus", "bus", "metro", "метро",
        "benzin", "бензин", "metan", "propan", "yoqilg", "zapravka", "moyka", "parkovka",
        "transport", "транспорт", "uber", "yandex", "indrive", "in driver", "go taxi"
    ]):
        return "Transport"

    # Aloqa
    if any(w in text for w in [
        "mobiuz", "uzmobile", "beeline", "ucell", "алоқа", "связь", "мобильн",
        "телефон", "aloqa", "internet", "интернет", "sim", "telefon", "mobile", "wifi", "vayfay"
    ]):
        return "Aloqa"

    # Kommunal / Uy
    if any(w in text for w in [
        "elektr", "электр", "kommunal", "коммун", "uy-joy", "gaz to‘lovi", "gaz tolovi",
        "suv to‘lovi", "suv tolovi", "ijara", "аренда", "rent", "heating", "kvartira", "domkom"
    ]):
        return "Kommunal" if any(w in text for w in ["kommunal", "коммун", "elektr", "электр", "to‘lovi", "tolovi", "gaz", "suv"]) else "Uy"

    # Sog'liq
    if any(w in text for w in [
        "shifokor", "врач", "klinika", "клиник", "dori", "лекар", "больниц",
        "медицин", "poliklinika", "sogliq", "med", "hospital", "apteka", "аптек",
        "dorixona", "stomatolog", "tish", "analiz"
    ]):
        return "Sog‘liq"

    # Ta'lim
    if any(w in text for w in [
        "ta'lim", "talim", "maktab", "школ", "университет", "учеб", "образован",
        "universitet", "kurs", "kitob", "o'quv", "oquv", "education", "school", "repetitor", "kontrakt"
    ]):
        return "Ta’lim"

    # Oziq-ovqat
    food_words = [
        "tushlik", "nonushta", "kechki ovqat", "ovqat", "somsa", "lavash", "doner", "burger",
        "pizza", "shashlik", "kfc", "evos", "oqtepa", "feed up", "coffee", "kofe", "choy",
        "non", "suv", "market", "korzinka", "makro", "havas", "carrefour", "baraka",
        "magazin", "bozor", "bazar", "restoran", "kafe", "еда", "продукт", "mahsulot"
    ]
    if re.search(r"\bosh\b", text) or any(w in text for w in food_words):
        return "Oziq-ovqat"

    # Kiyim-kechak
    if any(w in text for w in [
        "kiyim", "poyabzal", "shim", "koylak", "ko'ylak", "tufli", "krossovka",
        "moda", "fashion", "zara", "waikiki", "boutique", "одежд", "обув"
    ]):
        return "Kiyim-kechak"

    # Ko'ngilochar
    if any(w in text for w in [
        "kinoteatr", "кино", "film", "park", "парк", "sayr", "rekreatsiya",
        "entertainment", "hobby", "attraksion", "konsert", "game", "steam"
    ]):
        return "Ko‘ngilochar"

    # Xaridlar
    if any(w in text for w in ["uzum", "wildberries", "aliexpress", "xarid", "xaridlar", "shop"]):
        return "Xaridlar"

    # O'tkazma
    if any(w in text for w in [
        "transfer", "перевод", "o'tkazma", "otkazma", "perevod", "pul ko'chirish", "pul tashladim"
    ]):
        return "O‘tkazma"

    # Fallback to income check
    if any(w in text for w in ["maosh", "ish haqi", "salary", "зарплат", "аванс", "oylik", "stipendiya"]):
        return "Ish haqi"
    if any(w in text for w in ["biznes", "business"]):
        return "Biznes"
    if any(w in text for w in ["sovg‘a", "sovga", "gift"]):
        return "Sovg‘a"

    return "Boshqa"


def parse_quick_entry(text):
    text = (text or "").strip()
    if not text:
        return None

    sms_lower = text.lower()
    is_sms = any(k in sms_lower for k in [
        "uzs", "karta", "terminal", "oplata", "to'lov", "tolov",
        "spisanie", "zachislenie", "ostatok", "qoldiq", "kod:"
    ])

    if is_sms:
        # Match amount near UZS / so'm or oplata / spisanie / zachislenie
        m = re.search(
            r'(?:oplata|to[\'’`]?lov|spisanie|списание|zachislenie|зачисление|perevod|перевод)?[:\s]*([0-9][0-9\s.,]*)\s*(?:uzs|so[\'’`]?m|сум)',
            text,
            re.IGNORECASE,
        )
        if m:
            raw_amt = m.group(1).replace(" ", "").replace("\xa0", "")
            if "," in raw_amt and "." in raw_amt:
                if raw_amt.rfind(",") > raw_amt.rfind("."):
                    raw_amt = raw_amt.replace(".", "").replace(",", ".")
                else:
                    raw_amt = raw_amt.replace(",", "")
            elif "," in raw_amt:
                parts = raw_amt.split(",")
                if len(parts) > 1 and len(parts[-1]) <= 2:
                    raw_amt = ".".join(parts)
                else:
                    raw_amt = "".join(parts)

            try:
                amt = float(raw_amt)
            except ValueError:
                amt = 0.0

            if any(k in sms_lower for k in ["zachislenie", "зачисление", "popolnenie", "пополнение", "prihod", "приход", "kirim"]):
                tx_type = "income"
            else:
                tx_type = "expense"

            merchant_match = re.search(
                r'(?:joy|mesto|место|terminal|терминал|xarid|komu|ot|от|dlya)[:\s]+([^.\n,;]+)',
                text,
                re.IGNORECASE,
            )
            desc = merchant_match.group(1).strip() if merchant_match else "Bank to‘lovi"
            cat = categorize_description(desc, tx_type)
            if tx_type == "income" and cat == "Boshqa":
                cat = "Ish haqi" if any(w in sms_lower for w in ["oylik", "maosh", "salary", "stipendiya"]) else "Qo‘shimcha daromad"
            return {"amount": amt, "type": tx_type, "category": cat, "description": desc, "is_sms": True}

    tx_type = "income" if text.startswith("+") else "expense"
    cleaned = text.lstrip("+-").strip()

    # --- Number extraction ---
    # Step 1: Handle decimal + suffix first: e.g. "3.5m", "1.5k", "2.5 ming"
    dec_re = re.compile(
        r'(?<!\d)(\d+[.,]\d+)\s*(k|к|ming|минг|mln|млн|million|миллион|m|м)\b',
        re.IGNORECASE,
    )
    dm = dec_re.search(cleaned)
    if dm:
        try:
            val = float(dm.group(1).replace(",", "."))
        except ValueError:
            val = None
        if val is not None:
            suffix = dm.group(2).lower()
            if suffix in ["k", "к", "ming", "минг"]:
                val *= 1000
            elif suffix in ["m", "м", "mln", "млн", "million", "миллион"]:
                val *= 1000000
            s, e = dm.span()
            amt = val
            desc = re.sub(r'\s+', ' ', (cleaned[:s] + " " + cleaned[e:]).strip())
            if any(w in desc.lower() for w in ["oylik", "maosh", "salary", "stipendiya", "avans", "bonus", "daromad", "kirim", "tushdi"]):
                tx_type = "income"
            if not desc:
                desc = "Daromad" if tx_type == "income" else "Xarajat"
            cat = categorize_description(desc, tx_type)
            return {"amount": amt, "type": tx_type, "category": cat, "description": desc, "is_sms": False}

    # Step 2: Collect all digit runs, merge adjacent ones separated only by whitespace
    # so "35 0000" -> "350000", "1 200 000" -> "1200000"
    tokens = [(m.start(), m.end(), m.group()) for m in re.finditer(r'\d+', cleaned)]
    if not tokens:
        return None

    sep_re = re.compile(r'^[\s\xa0]+$')
    groups = []
    cur_start, cur_end, cur_digits = tokens[0]
    for i in range(1, len(tokens)):
        gap = cleaned[cur_end:tokens[i][0]]
        if sep_re.match(gap) and len(cur_digits) + len(tokens[i][2]) <= 15:
            cur_digits += tokens[i][2]
            cur_end = tokens[i][1]
        else:
            groups.append((cur_start, cur_end, cur_digits))
            cur_start, cur_end, cur_digits = tokens[i]
    groups.append((cur_start, cur_end, cur_digits))

    best_val, best_start, best_end, best_has_suffix = None, None, None, False
    for (gs, ge, digits) in groups:
        after = cleaned[ge:]
        sm = re.match(r'^\s*(k|к|ming|минг|mln|млн|million|миллион|m|м)\b', after, re.IGNORECASE)
        suffix = sm.group(1).lower() if sm else ""
        after_end = ge + sm.end() if sm else ge
        # Skip suffix if it's part of a word (e.g. "kfc", "market")
        if sm:
            tail = cleaned[after_end:]
            if tail and tail[0].isalpha():
                suffix = ""
                after_end = ge
        try:
            val = float(digits)
        except ValueError:
            continue
        has_suffix = bool(suffix)
        if suffix in ["k", "к", "ming", "минг"]:
            val *= 1000
        elif suffix in ["m", "м", "mln", "млн", "million", "миллион"]:
            val *= 1000000
        # Prefer: has_suffix > no suffix; then larger value
        if (best_val is None
                or (has_suffix and not best_has_suffix)
                or (has_suffix == best_has_suffix and val > best_val)):
            best_val, best_start, best_end, best_has_suffix = val, gs, after_end, has_suffix

    if best_val is None:
        return None

    amt = best_val
    desc = re.sub(r'\s+', ' ', (cleaned[:best_start] + " " + cleaned[best_end:]).strip())

    if any(w in desc.lower() for w in ["oylik", "maosh", "salary", "stipendiya", "avans", "bonus", "daromad", "kirim", "tushdi"]):
        tx_type = "income"
    if not desc:
        desc = "Daromad" if tx_type == "income" else "Xarajat"

    cat = categorize_description(desc, tx_type)
    return {"amount": amt, "type": tx_type, "category": cat, "description": desc, "is_sms": False}
