@echo off
REM Windows batch file to set up email notifications and daily reports
REM Save this as setup_email.bat

echo 📧 Conference Room Booking System - Email Setup
echo ===============================================
echo.

echo This script will help you:
echo 1. Configure email credentials
echo 2. Test email functionality
echo 3. Set up automated daily reports
echo.

echo STEP 1: Configure Email Credentials
echo -----------------------------------
echo.
echo For Gmail, you need:
echo - Your Gmail address (e.g., mybusiness@gmail.com)
echo - An App Password (NOT your regular password)
echo.
echo To get an App Password:
echo 1. Enable 2-factor authentication on your Google account
echo 2. Go to: https://myaccount.google.com/security
echo 3. Click "App passwords" under "2-Step Verification"
echo 4. Generate a password for "Mail"
echo.

set /p EMAIL_USER="Enter your email address: "
set /p EMAIL_PASSWORD="Enter your app password: "
set /p TEST_EMAIL="Enter test email address (can be same as above): "

echo.
echo Setting environment variables...
setx EMAIL_USER "%EMAIL_USER%"
setx EMAIL_PASSWORD "%EMAIL_PASSWORD%"
setx TEST_EMAIL "%TEST_EMAIL%"
setx EMAIL_HOST "smtp.gmail.com"
setx EMAIL_PORT "587"

echo.
echo ✅ Environment variables set! 
echo ⚠️  Please restart your PowerShell/Command Prompt for changes to take effect.
echo.

echo STEP 2: Test Email System
echo -------------------------
echo After restarting your terminal, run:
echo   python test_scheduler.py test-all
echo.

echo STEP 3: Set Up Daily Reports (Optional)
echo ---------------------------------------
echo To automatically send daily reports at 5 PM:
echo.
echo Option A - Windows Task Scheduler:
echo 1. Open Task Scheduler (taskschd.msc)
echo 2. Create Basic Task
echo 3. Name: "Daily Booking Report"
echo 4. Trigger: Daily at 5:00 PM
echo 5. Action: Start a program
echo 6. Program: python
echo 7. Arguments: "%CD%\run_daily_report.py"
echo 8. Start in: "%CD%"
echo.
echo Option B - Manual Testing:
echo Run: python test_scheduler.py test-report
echo.

pause
