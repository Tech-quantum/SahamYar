# SahamYar - Termux Commands

این راهنما برای توسعه و تست محلی پروژه در Termux است. پیش از هر دستور تغییردهنده، وضعیت Git را بررسی کن.

## مسیر پروژه

    cd ~/SahamYar/repo-check

## بررسی وضعیت مخزن

    cd ~/SahamYar/repo-check
    git status --short --branch
    git branch --show-current
    git log -1 --oneline
    git diff --stat
    git diff --check

فایل‌های untracked را قبل از هر تصمیم درباره حذف، جابه‌جایی یا commit بررسی کن.

## تست بک‌اند

    cd ~/SahamYar/repo-check/backend
    python -m pytest -q

برای تست مشخص:

    python -m pytest tests/test_tsetmc.py -q

نصب وابستگی‌های توسعه در صورت نیاز:

    python -m pip install -e '.[dev]'

## اجرای بک‌اند محلی

    cd ~/SahamYar/repo-check/backend
    python -m app.main

سرور توسعه روی 127.0.0.1:8000 گوش می‌دهد. اجرای این دستور scheduler محلی را نیز فعال می‌کند. برای production از Flask development server استفاده نکن؛ lifecycle پردازش‌های پس‌زمینه و هماهنگی چند worker هنوز نیازمند طراحی جداگانه است.

## تست و ساخت اندروید

از ریشه مخزن:

    cd ~/SahamYar/repo-check
    ./gradlew testDebugUnitTest --rerun-tasks
    ./gradlew assembleDebug

اجرای هر دو مرحله در یک فرمان:

    ./gradlew testDebugUnitTest assembleDebug

مسیر معمول APK دیباگ:

    app/build/outputs/apk/debug/app-debug.apk

تنظیمات فعلی Android: compileSdk/targetSdk برابر 36، minSdk برابر 26 و JVM target برابر 17.

## بررسی تغییرات

    cd ~/SahamYar/repo-check
    git diff
    git diff --cached
    git status --short

## ساخت آرشیو بررسی محلی

این آرشیو برای تحویل وضعیت محلی است و به‌معنی commit یا backup در GitHub نیست.

    cd ~/SahamYar/repo-check || exit 1
    OUT="$HOME/SahamYar-audit-$(date +%Y%m%d-%H%M%S).tar.gz"
    TMP="$(mktemp -d)" || exit 1

    git status --short --branch > "$TMP/status.txt"
    git diff > "$TMP/worktree.diff"
    git diff --cached > "$TMP/staged.diff"
    git branch --show-current > "$TMP/branch.txt"
    git log -1 --oneline > "$TMP/head.txt"

    tar -czf "$OUT" \
      --exclude='.git' \
      --exclude='.venv' \
      --exclude='venv' \
      --exclude='__pycache__' \
      --exclude='*.pyc' \
      backend app AGENTS.md README.md STATUS.txt \
      ROADMAP_DEFERRED.md HISTORY.md TERMUX_COMMANDS.md \
      "Handoff Document.txt" \
      "$TMP/status.txt" "$TMP/worktree.diff" \
      "$TMP/staged.diff" "$TMP/branch.txt" "$TMP/head.txt"

    RESULT=$?
    rm -r "$TMP"

    if [ "$RESULT" -eq 0 ]; then
      echo "Archive created: $OUT"
      ls -lh "$OUT"
      mkdir -p /sdcard/Download
      cp "$OUT" /sdcard/Download/
      echo "Copied to /sdcard/Download/"
    else
      echo "Archive creation failed. Check project paths."
    fi

اگر پوشه یا فایلی در نسخه محلی وجود ندارد، پیش از تغییر آرگومان‌های آرشیو مسیر واقعی را بررسی کن.

## نکات مهم

- پیش از pull یا تغییر branch، git status را بررسی کن.
- فقط در صورت نبود تغییر tracked محلی از git pull --ff-only origin main استفاده کن.
- از git reset --hard، git clean، force-push و دستورهای مخرب استفاده نکن.
- بدون تأیید صریح، commit، push یا merge انجام نده.
- هشدار Android SDK manager درباره دریافت manifestها را با نتیجه نهایی Gradle اشتباه نگیر؛ فقط وضعیت taskها و کد خروجی Build ملاک است.
- نتایج تست ثبت‌شده در STATUS.txt مربوط به snapshot مشخص‌شده‌اند؛ پس از تغییر کد، تست‌ها را دوباره اجرا کن.
