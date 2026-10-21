@echo off
chcp 65001 >nul
title Discord Music Bot - 1-Click Runner
cd /d "%~dp0"

echo ================================================================
echo       🎵 DISCORD MUSIC BOT - تشغيل البوت بضغطة واحدة 🎵
echo ================================================================
echo.

:: 1. Check Python installation
set "PY_CMD=python"
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    py --version >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set "PY_CMD=py"
    ) else (
        echo [!] خطأ: بايثون (Python) غير مثبت على هذا الجهاز.
        echo [!] يتم الآن فتح صفحة تحميل بايثون الرسمية...
        start https://www.python.org/downloads/
        echo.
        echo يرجى تثبيت Python ثم إعادة تشغيل هذا الملف.
        echo (مهم: ضع علامة صح على "Add python.exe to PATH" أثناء التثبيت)
        echo.
        pause
        exit /b 1
    )
)

echo [+] تم العثور على Python:
%PY_CMD% --version
echo.

:: 2. Check and setup Virtual Environment (First time run)
if not exist "venv\Scripts\python.exe" (
    echo [*] جاري إعداد بيئة التشغيل لأول مرة (First-Time Setup)...
    echo [*] يتم الآن إنشاء المجلد الافتراضي venv...
    %PY_CMD% -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo [!] تعذر إنشاء venv، سيتم استخدام بايثون المباشر.
        set "RUN_PY=%PY_CMD%"
    ) else (
        set "RUN_PY=venv\Scripts\python.exe"
    )

    echo [*] جاري تثبيت وتحديث المكتبات المطلوبة (Requirements)...
    if exist "venv\Scripts\python.exe" (
        venv\Scripts\python.exe -m pip install --quiet --upgrade pip
        venv\Scripts\pip.exe install -r requirements.txt
    ) else (
        %PY_CMD% -m pip install -r requirements.txt
    )
    echo [OK] تم تثبيت كافة المكتبات بنجاح!
    echo.
) else (
    set "RUN_PY=venv\Scripts\python.exe"
)

:: 3. Check FFmpeg
where ffmpeg >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    if not exist "bin\ffmpeg.exe" (
        if not exist "ffmpeg.exe" (
            echo [*] فحص برنامج معالجة الصوت FFmpeg...
            where winget >nul 2>&1
            if %ERRORLEVEL% EQU 0 (
                echo [*] جاري تثبيت FFmpeg تلقائياً عبر Winget...
                winget install Gyan.FFmpeg --accept-source-agreements --accept-package-agreements --silent
            ) else (
                echo [!] تنبيه: FFmpeg غير موجود في PATH، سيتم البحث في المجلدات البديلة.
            )
        )
    )
)

:: 4. Start the Bot
echo ================================================================
echo       🚀 جاري تشغيل بوت الديسكورد الآن... (الرجاء عدم إغلاق النافذة)
echo ================================================================
echo.

%RUN_PY% src/bot.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] توقف البوت مع كود خطأ: %ERRORLEVEL%
    echo اضغط أي زر لإعادة المحاولة...
    pause
    goto :eof
)
