# فرمان‌های Termux برای سهام‌یار

مسیر پروژه:
```bash
cd ~/SahamYar/repo-check
```

## وضعیت بدون تغییر
```bash
git status --short
git branch --show-current
git log -1 --oneline
```

## حقیقت‌سنجی Codal / financial
```bash
find backend -type f \( -name '*codal*' -o -name '*financial*' \) | sort
```
```bash
grep -n -E 'codal|financial_service|financial-reports|fundamental' backend/app/main.py | head -40
```
```bash
grep -R -n -E 'financial-reports|FinancialReport|Codal' app/src/main 2>/dev/null | head -40
```

## diff ایمن
```bash
git diff -- backend/app/main.py
git diff --stat
git diff --check
```

## تست بک‌اند
```bash
cd ~/SahamYar/repo-check/backend
../.venv/bin/python -m pytest -q
```
(اگر venv جای دیگری است، مسیر python پروژه را جایگزین کنید.)

## ساخت اندروید
```bash
./gradlew :app:compileDebugKotlin
./gradlew :app:assembleDebug
```

## قواعد ایمنی
- هر بار یک فرمان؛ خروجی را بخوان.
- قبل از ویرایش، فایل و diff را ببین.
- کار محلی را پاک نکن.
- از reset --hard و clean بدون اجازه استفاده نکن.
- عملیات stage/commit/push/merge فقط با اجازه صریح مالک پروژه.
