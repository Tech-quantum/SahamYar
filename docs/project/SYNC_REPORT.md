# گزارش هم‌ترازی مستندات و مخزن — سهام‌یار

تاریخ هم‌ترازی: ۱۴۰۵/۰۹/۰۵ (۲۶ نوامبر ۲۰۲۶)
مرجع کد بررسی‌شده: Tech-quantum/SahamYar، شاخه main، commit 97107538c42fb0548a367971c540591efc6d663d.

## نتیجه مقایسه
بسته مستندات ۲۶ نوامبر از نظر شرح پیشرفت محصول، نقشه راه و مسائل باز کامل‌تر از مستندات ریشه مخزن در ۲۱ نوامبر است؛ اما برای وضعیت کد commitشده، main مرجع حقیقت است. README قبلی مخزن routeهای Codal HTTP را معرفی می‌کرد که در backend/app/main.py وجود ندارند.

## واقعیت تأییدشده روی main

### بک‌اند
- Flask + TSETMC: جست‌وجو، مشخصات، قیمت، تاریخچه و تحلیل تکنیکال SMA/EMA/RSI/MACD.
- backend/app/providers/codal.py: parser و استانداردسازی HTML آفلاین برای صورت‌های مالی.
- codal_client.py، financial_service.py و routeهای /api/v1/codal/... یا financial-reports در main یافت نشدند.
- در GET /api/v1/stocks/<ins_code>/analysis لایه fundamental همیشه UNAVAILABLE است.

### اندروید
- فایل‌های ApiClient.kt، StockApiService.kt، StockRepository.kt و StockAnalysisResponse.kt در main وجود دارند.
- ApiClient.BASE_URL برابر http://127.0.0.1:8000/ است؛ این مانع انتشار مستقل APK است.
- StockAnalysisResponse در main فیلد data از نوع JsonElement ندارد.
- TsetmcMarketApi.kt در main یافت نشد؛ اتصال مستقیم TSETMC اندروید فقط به‌عنوان پیشرفت محلی گزارش‌شده ثبت می‌شود.

## پیشرفت‌های محلی گزارش‌شده، نه تأییدشده در main
1. اتصال مستقیم TSETMC در اندروید و کارکرد جست‌وجو، قیمت، تاریخچه و شاخص‌ها.
2. ساخت موفق compileDebugKotlin و assembleDebug و نصب APK طبق گزارش کاربر.
3. وجود سرویس Codal و endpointهای financial-reports در worktree محلی؛ نیازمند بررسی مستقیم Termux.

## ساختار مستندات این شاخه
- README_PROJECT.md: معرفی و دامنه محصول
- SYNC_REPORT.md: گزارش مقایسه و منبع حقیقت
- STATUS.txt: وضعیت فعلی
- ROADMAP.md: نقشه راه
- OPEN_ISSUES.md: مسائل باز
- HISTORY.md: تاریخچه
- HANDOFF.md: نقطه ادامه کار
- TERMUX_COMMANDS.md: فرمان‌های ایمن
- backend_README.md: مستند فنی بک‌اند مطابق کد main

## اقدام GitHub
این مجموعه روی شاخه مستقل docs/sync-project-documentation-2026-11-26 قرار می‌گیرد و برای بازبینی از طریق Pull Request ارائه می‌شود. شاخه main در این مرحله مستقیماً تغییر داده نمی‌شود. فایل‌ها فقط مستندات‌اند و هیچ کد اجرایی تغییر نمی‌کند.

## محدودیت
وضعیت worktree محلی Termux از راه GitHub قابل اثبات نیست. هر ادعای مربوط به فایل‌ها و تست‌های محلی باید با خروجی واقعی همان محیط تأیید شود.
