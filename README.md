# Smart Wallet

Shaxsiy kirim-chiqimlarni kuzatish va turli banklardan olingan Excel/CSV oborotkalarni import qilish uchun boshlang‘ich web-ilova.

## Ishga tushirish

1. Kompyuterga Python 3.10 yoki undan yangisini o‘rnating.
2. Loyihaning papkasida terminal oching.
3. Quyidagilarni bajaring:

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Brauzerda lokal manzil ochiladi (odatda http://localhost:8501).

## Imkoniyatlar
- Dashboard: balans, tanlangan davr uchun kirim-chiqim, kundalik yoki oylik xarajatlar dinamikasi va kategoriyalar.
- Davr filtrlari: bugun, 7 kun, 30 kun yoki barcha ma’lumotlar.
- Excel import: XLSX, XLS, CSV.
- Faylni yuklagandan keyin **Faylni o‘qish va saralash** tugmasi bilan sana, summa, izoh, kategoriya va operatsiya turini avtomatik aniqlab import qilish.
- Telegram Bot orqali tezkor matnli kiritish (masalan: `45000 tushlik`, `20k taksi`, `+5m oylik`) hamda Click/Payme SMS xabarlarini avtomatik tanib olish.
- Telegram orqali kiritilgan operatsiyani bir bosishda bekor qilish yoki kategoriyasini o‘zgartirish tugmalari.
- Takroriy tranzaksiyalarni fingerprint orqali cheklash.
- Tranzaksiyalar tarixi, qidiruv va sana/kategoriya filtri.
- Qo‘lda kirim/chiqim kiritish.
- Xarajat va daromad uchun alohida kategoriyalar hamda izoh bo‘yicha kategoriya taklifi.
- Kategoriya bo‘yicha oylik byudjet limiti va sarf holati.
- Ma’lumotlar lokal SQLite bazasida saqlanadi (`smart_wallet.db`).

## Muhim
- Bu MVP bank hisobiga bevosita ulanmaydi; bankdan yuklab olingan faylni import qiladi.
- Import ustunlarni sarlavha va qiymatlardan aniqlaydi; aniqlangan ustunlar hamda o‘tkazib yuborilgan qatorlar natijada ko‘rsatiladi.
- Fayllarda karta raqami, hisob raqami yoki shaxsiy ma’lumotlar bo‘lsa, ulashishdan oldin ularni yashiring.
- Hisoblangan qoldiq import qilingan barcha yozuvlar yig‘indisidir; bankdagi real balans bilan solishtirib tekshirish kerak.

## Telegram botni ulash (Windows)

1. Telegram’da `@BotFather` ni oching, `/newbot` yuboring, bot nomi va username belgilang. U bergan tokenni xavfsiz saqlang va kodga yoki ochiq chatga yubormang.
2. Telegram’da `@userinfobot` га `Start` bosing va o‘zingizning raqamli Telegram ID’ingizni oling.
3. Loyihaning papkasida yangi PowerShell oynasini oching. Bot tokeni va Telegram ID’ni muhit o‘zgaruvchilariga kiriting:

   ```powershell
   $env:TELEGRAM_BOT_TOKEN="BotFather bergan token"
   $env:TELEGRAM_ALLOWED_USER_ID="Sizning raqamli Telegram ID"
   ```

4. Botni ishga tushiring:

   ```powershell
   cd D:\hamyon
   python -m pip install -r requirements.txt
   python bot.py
   ```

5. Telegram’da yangi botga `/start` yuboring. `/balance`, `/recent`, `/add` buyruqlari bilan balansni ko‘ring, oxirgi operatsiyalarni tekshiring yoki kirim/chiqim qo‘shing.
6. Streamlit ilovasini boshqa terminal oynasida ishga tushiring (`streamlit run app.py`). Bot va web-ilova bir xil `smart_wallet.db` faylidan foydalanadi. Bot terminalini ochiq qoldiring; to‘xtatish uchun `Ctrl+C` bosing.

Bot lokal polling rejimida ishlaydi; webhook yoki ommaviy server talab qilinmaydi. Bot javob berishi uchun kompyuter yoqilgan va internetga ulangan bo‘lishi kerak. Ruxsat berilgan yagona Telegram ID ma’lumotlarni ko‘rishi yoki o‘zgartirishi mumkin.

## Telegram ichida mobil dashboardni ochish

Botdagi **Smart Wallet’ni ochish** tugmasi ayni Streamlit dashboardni Telegram Mini App ichida ochadi. Mobil ko‘rinish dashboardni almashtirmaydi; faqat telefon ekraniga moslab nav, kartalar va jadvallarni ko‘rsatadi.

Telegram `localhost` manziliga ulana olmaydi. HTTPS ommaviy manzil kerak. Doimiy ishlatish uchun HTTPS bilan himoyalangan hosting tavsiya qilinadi. Sinov uchun Cloudflare Quick Tunnel’dan foydalanish mumkin:

1. Streamlit’ni `8501` portida ishga tushiring.
2. `cloudflared` o‘rnatilgan boshqa terminalda tunnel oching:

   ```powershell
   cloudflared tunnel --url http://localhost:8501
   ```

3. Terminal ko‘rsatgan `https://...trycloudflare.com` manzilni nusxalang. Tunnel terminalini ochiq qoldiring.
4. Streamlit’ni to‘xtatib, shu manzil va kuchli kirish paroli bilan qayta ishga tushiring:

   ```powershell
   cd D:\hamyon
   $env:TELEGRAM_WEBAPP_URL="https://...trycloudflare.com"
   $env:SMART_WALLET_ACCESS_PASSWORD="o‘zingiz tanlagan kuchli PIN yoki parol"
   python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
   ```

5. Botni boshqa terminalda ishga tushiring; bot terminalida `TELEGRAM_BOT_TOKEN` va `TELEGRAM_ALLOWED_USER_ID` bilan birga xuddi shu `TELEGRAM_WEBAPP_URL` ni sozlang:

   ```powershell
   cd D:\hamyon
   $env:TELEGRAM_BOT_TOKEN="BotFather bergan token"
   $env:TELEGRAM_ALLOWED_USER_ID="Telegram ID raqamingiz"
   $env:TELEGRAM_WEBAPP_URL="https://...trycloudflare.com"
   python bot.py
   ```

6. Telegram botga `/start` yoki `/app` yuboring, **Smart Wallet’ni ochish** tugmasini bosing va kirish PIN/parolini kiriting. Login’dan keyin botdagi va web dashboard’dagi ma’lumotlar bir xil SQLite bazasidan ko‘rinadi.

Ommaviy manzilni begonalarga ulashmang. Web-ilova `SMART_WALLET_ACCESS_PASSWORD` o‘rnatilmasa ishga tushishni to‘xtatadi. Quick Tunnel manzili vaqtinchalik; qayta ishga tushirilganda URL o‘zgarishi mumkin, shunda `TELEGRAM_WEBAPP_URL` ni Streamlit va botda yangilash kerak. Haqiqiy maxfiy tokenlarni README yoki kodga yozmang.
