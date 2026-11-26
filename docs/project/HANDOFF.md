# سند تحویل و ادامه کار — سهام‌یار
تاریخ: ۱۴۰۵/۰۹/۰۵ (2026-11-26)

## نقطه توقف
هدف جاری: اتصال تحلیل بنیادی Codal به مسیر تحلیل نماد — پس از تأیید وجود کد واقعی روی worktree.

### مرجع بررسی GitHub
مخزن Tech-quantum/SahamYar، شاخه main، snapshot بررسی‌شده: 97107538c42fb0548a367971c540591efc6d663d.

## روی main (تأییدشده)
- backend/app/providers/codal.py: parser + standardize_financial_report
- GET /api/v1/stocks/<ins_code>/analysis: fundamental ثابت UNAVAILABLE
- مدل اندروید StockAnalysisResponse.kt با لایه‌ها موجود است (بدون فیلد data در نسخه main).
- ApiClient.kt و StockApiService.kt موجودند؛ ApiClient از http://127.0.0.1:8000/ استفاده می‌کند که برای APK مستقل مانع انتشار است.

## گزارش محلی (نیاز به تأیید روی دستگاه)
- سرویس/endpointهای Codal یا financial-reports
- اتصال مستقیم TSETMC در اندروید و فایل‌هایی مانند TsetmcMarketApi.kt
- فرمان پیشنهادی:
```bash
cd ~/SahamYar/repo-check && find backend -type f \( -name '*codal*' -o -name '*financial*' \) | sort && echo '---' && grep -n -E 'codal|financial_service|financial-reports|fundamental' backend/app/main.py | head -40
```

## یافته قطعی درباره Codal روی main
- README پیشین مخزن سه route برای Codal HTTP را ادعا می‌کرد، اما backend/app/main.py هیچ‌کدام را ثبت نکرده است.
- backend/app/providers/codal.py پارسر آفلاین است؛ codal_client.py و financial_service.py در main وجود ندارند.
- تست‌های backend/tests/test_codal.py مربوط به پارسرند؛ routeهای Codal در backend/tests/test_api.py مشاهده نشدند.

## یافته قطعی درباره fundamental روی main
- هیچ فراخوانی سرویس Codal داخل get_stock_analysis نیست.
- پیام لایه: «منبع معتبر داده‌های بنیادی هنوز متصل نشده است.»
- تست API انتظار UNAVAILABLE بودن fundamental را دارد.

## روش همکاری
- فارسی، فنی، مستقیم.
- هر بار یک دستور کوتاه؛ منتظر خروجی بمان.
- قبل از ویرایش: خواندن فایل فعلی + git diff همان مسیر.
- پس از اصلاح: تست مرتبط و ثبت نتیجه واقعی.
- موفقیت فقط بر اساس خروجی مشاهده‌شده.

## قواعد Git
هرگز reset --hard، git checkout برای دور انداختن کار، یا git clean بدون اجازه اجرا نشود. تغییرات محلی حفظ شوند.
