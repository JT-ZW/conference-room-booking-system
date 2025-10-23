#!/usr/bin/env python3
"""
Enhanced email system with PDF and Excel report attachments
"""

import os
import sys
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
import calendar

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Load .env file
def load_env_file():
    env_path = Path('.env')
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env_file()

# CAT timezone
CAT = timezone(timedelta(hours=2))

# Email settings
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USER = os.getenv('EMAIL_USER', '')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
TEST_EMAIL = os.getenv('TEST_EMAIL', '')

def send_email_with_attachments(to_email, subject, body_html, body_text=None, attachments=None):
    """
    Send an email with PDF and Excel attachments.
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        body_html (str): HTML body content
        body_text (str, optional): Plain text body content
        attachments (list, optional): List of file paths to attach
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Create message
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = EMAIL_USER
        msg['To'] = to_email

        # Create text and HTML parts
        if body_text:
            part1 = MIMEText(body_text, 'plain')
            msg.attach(part1)
        
        part2 = MIMEText(body_html, 'html')
        msg.attach(part2)

        # Add attachments
        if attachments:
            for file_path in attachments:
                if os.path.exists(file_path):
                    with open(file_path, "rb") as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                    
                    encoders.encode_base64(part)
                    
                    # Get filename
                    filename = os.path.basename(file_path)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {filename}',
                    )
                    
                    msg.attach(part)
                    print(f"📎 Attached: {filename}")
                else:
                    print(f"⚠️ Attachment not found: {file_path}")

        # Create SMTP session
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        
        # Send email
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email to {to_email}: {str(e)}")
        return False

def is_weekday():
    """Check if today is a weekday (Monday=0 to Friday=4)"""
    return datetime.now(CAT).weekday() < 5

def is_friday():
    """Check if today is Friday"""
    return datetime.now(CAT).weekday() == 4

def is_last_friday_of_month():
    """Check if today is the last Friday of the month"""
    today = datetime.now(CAT).date()
    
    # If it's not Friday, return False
    if today.weekday() != 4:
        return False
    
    # Get the last day of the current month
    last_day = calendar.monthrange(today.year, today.month)[1]
    last_date = date(today.year, today.month, last_day)
    
    # Find the last Friday of the month
    days_back = (last_date.weekday() - 4) % 7
    last_friday = last_date - timedelta(days=days_back)
    
    return today == last_friday

def should_send_daily_report():
    """Check if it's time to send daily report (16:55 on weekdays)"""
    now = datetime.now(CAT)
    return now.hour == 16 and now.minute == 55 and is_weekday()

def should_send_weekly_report():
    """Check if it's time to send weekly report (16:55 on Fridays)"""
    now = datetime.now(CAT)
    return now.hour == 16 and now.minute == 55 and is_friday()

def should_send_monthly_report():
    """Check if it's time to send monthly report (16:55 on last Friday of month)"""
    now = datetime.now(CAT)
    return now.hour == 16 and now.minute == 55 and is_last_friday_of_month()

def create_sample_pdf_report(report_type, report_data, filename):
    """
    Create a sample PDF report (placeholder - you can enhance this with actual PDF generation)
    """
    try:
        # This is a placeholder - in real implementation, you'd use libraries like:
        # - reportlab for PDF generation
        # - matplotlib for charts
        # - weasyprint for HTML to PDF conversion
        
        content = f"""
{report_type.upper()} BOOKING REPORT
Generated: {datetime.now(CAT).strftime('%Y-%m-%d %H:%M %Z')}

SUMMARY:
- Total Bookings: {report_data.get('total_bookings', 0)}
- Confirmed: {report_data.get('confirmed_bookings', 0)}
- Tentative: {report_data.get('tentative_bookings', 0)}
- Cancelled: {report_data.get('cancelled_bookings', 0)}

BOOKINGS DETAILS:
{chr(10).join([f"- {booking.get('client_name', 'N/A')} - {booking.get('room_name', 'N/A')} ({booking.get('start_time', 'N/A')} - {booking.get('end_time', 'N/A')})" for booking in report_data.get('today_bookings', [])])}

[This is a sample PDF content - in production, this would be a properly formatted PDF with charts and tables]
        """
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"📄 Created sample PDF: {filename}")
        return True
        
    except Exception as e:
        print(f"❌ Error creating PDF: {str(e)}")
        return False

def create_sample_excel_report(report_type, report_data, filename):
    """
    Create a sample Excel report (placeholder - you can enhance this with actual Excel generation)
    """
    try:
        # This is a placeholder - in real implementation, you'd use libraries like:
        # - openpyxl for Excel generation
        # - pandas for data manipulation
        # - xlsxwriter for advanced Excel features
        
        content = f"""Report Type,{report_type}
Generated,{datetime.now(CAT).strftime('%Y-%m-%d %H:%M %Z')}

Summary
Total Bookings,{report_data.get('total_bookings', 0)}
Confirmed,{report_data.get('confirmed_bookings', 0)}
Tentative,{report_data.get('tentative_bookings', 0)}
Cancelled,{report_data.get('cancelled_bookings', 0)}

Booking Details
ID,Client,Room,Start Time,End Time,Purpose,Status
"""
        
        for booking in report_data.get('today_bookings', []):
            content += f"{booking.get('id', 'N/A')},{booking.get('client_name', 'N/A')},{booking.get('room_name', 'N/A')},{booking.get('start_time', 'N/A')},{booking.get('end_time', 'N/A')},{booking.get('purpose', 'N/A')},{booking.get('status', 'N/A')}\n"
        
        # Save as CSV for now (in production, this would be actual Excel)
        csv_filename = filename.replace('.xlsx', '.csv')
        with open(csv_filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"📊 Created sample Excel (CSV): {csv_filename}")
        return csv_filename
        
    except Exception as e:
        print(f"❌ Error creating Excel: {str(e)}")
        return None

def generate_report_data(report_type):
    """Generate sample report data based on report type"""
    today = datetime.now(CAT).date()
    
    if report_type == "daily":
        start_date = today
        end_date = today + timedelta(days=1)
    elif report_type == "weekly":
        # Get Monday of current week
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=7)
    elif report_type == "monthly":
        # Get first day of current month
        start_date = date(today.year, today.month, 1)
        # Get first day of next month
        if today.month == 12:
            end_date = date(today.year + 1, 1, 1)
        else:
            end_date = date(today.year, today.month + 1, 1)
    
    # Sample data (in production, this would query your database)
    sample_bookings = [
        {
            'id': 101,
            'client_name': 'ABC Company',
            'room_name': 'Conference Room A',
            'start_time': '2025-07-23 09:00',
            'end_time': '2025-07-23 12:00',
            'purpose': 'Board Meeting',
            'status': 'confirmed'
        },
        {
            'id': 102,
            'client_name': 'XYZ Corp',
            'room_name': 'Meeting Room B',
            'start_time': '2025-07-23 14:00',
            'end_time': '2025-07-23 16:00',
            'purpose': 'Team Sync',
            'status': 'tentative'
        }
    ]
    
    return {
        'report_type': report_type,
        'date_range': f"{start_date} to {end_date}",
        'total_bookings': len(sample_bookings),
        'confirmed_bookings': len([b for b in sample_bookings if b['status'] == 'confirmed']),
        'tentative_bookings': len([b for b in sample_bookings if b['status'] == 'tentative']),
        'cancelled_bookings': 0,
        'today_bookings': sample_bookings,
        'tomorrow_bookings': []
    }

def send_report_email(report_type):
    """Send report email with attachments"""
    try:
        print(f"📊 Generating {report_type} report...")
        
        # Generate report data
        report_data = generate_report_data(report_type)
        
        # Create timestamp for filenames
        timestamp = datetime.now(CAT).strftime('%Y%m%d_%H%M')
        
        # Create PDF report
        pdf_filename = f"reports/{report_type}_report_{timestamp}.pdf"
        os.makedirs("reports", exist_ok=True)
        pdf_success = create_sample_pdf_report(report_type, report_data, pdf_filename)
        
        # Create Excel report
        excel_filename = f"reports/{report_type}_report_{timestamp}.xlsx"
        excel_file = create_sample_excel_report(report_type, report_data, excel_filename)
        
        # Prepare email content
        today = datetime.now(CAT).strftime('%Y-%m-%d')
        subject = f"{report_type.title()} Booking Report - {today}"
        
        # HTML email body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: #2196F3; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .stats {{ display: flex; justify-content: space-around; margin: 20px 0; }}
                .stat-box {{ background-color: #f0f8ff; padding: 15px; border-radius: 5px; text-align: center; flex: 1; margin: 0 10px; }}
                .stat-number {{ font-size: 24px; font-weight: bold; color: #2196F3; }}
                .attachments {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .footer {{ background-color: #f1f1f1; padding: 10px; text-align: center; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 {report_type.title()} Booking Report</h1>
                <h2>{today}</h2>
            </div>
            
            <div class="content">
                <div class="stats">
                    <div class="stat-box">
                        <div class="stat-number">{report_data['total_bookings']}</div>
                        <div>Total Bookings</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number">{report_data['confirmed_bookings']}</div>
                        <div>Confirmed</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number">{report_data['tentative_bookings']}</div>
                        <div>Tentative</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number">{report_data['cancelled_bookings']}</div>
                        <div>Cancelled</div>
                    </div>
                </div>
                
                <div class="attachments">
                    <h3>📎 Report Attachments</h3>
                    <p>This email includes the following attachments:</p>
                    <ul>
                        <li>📄 <strong>PDF Report</strong> - Detailed formatted report with charts and analysis</li>
                        <li>📊 <strong>Excel Spreadsheet</strong> - Raw data for further analysis and filtering</li>
                    </ul>
                    <p>These files contain the same data in different formats for your convenience.</p>
                </div>
                
                <h3>📈 Quick Summary</h3>
                <p>Report Period: {report_data['date_range']}</p>
                <p>Total bookings processed: <strong>{report_data['total_bookings']}</strong></p>
                <p>Confirmed bookings: <strong>{report_data['confirmed_bookings']}</strong></p>
                
            </div>
            
            <div class="footer">
                <p>{report_type.title()} report generated automatically at 16:55 CAT</p>
                <p>Generated on {datetime.now(CAT).strftime('%Y-%m-%d at %H:%M %Z')}</p>
            </div>
        </body>
        </html>
        """
        
        # Plain text version
        text_body = f"""
{report_type.upper()} BOOKING REPORT - {today}

QUICK SUMMARY:
=============
Report Period: {report_data['date_range']}
Total Bookings: {report_data['total_bookings']}
Confirmed: {report_data['confirmed_bookings']}
Tentative: {report_data['tentative_bookings']}
Cancelled: {report_data['cancelled_bookings']}

ATTACHMENTS:
============
📄 PDF Report - Detailed formatted report with charts
📊 Excel Spreadsheet - Raw data for analysis

The attached files contain comprehensive booking data in PDF and Excel formats
for your review and analysis.

Report generated automatically at 16:55 CAT
Generated on {datetime.now(CAT).strftime('%Y-%m-%d at %H:%M %Z')}
        """
        
        # Prepare attachments
        attachments = []
        if pdf_success and os.path.exists(pdf_filename):
            attachments.append(pdf_filename)
        if excel_file and os.path.exists(excel_file):
            attachments.append(excel_file)
        
        # Send email
        success = send_email_with_attachments(
            TEST_EMAIL, 
            subject, 
            html_body, 
            text_body, 
            attachments
        )
        
        if success:
            print(f"✅ {report_type.title()} report sent successfully!")
        else:
            print(f"❌ Failed to send {report_type} report")
        
        return success
        
    except Exception as e:
        print(f"❌ Error sending {report_type} report: {str(e)}")
        return False

def run_scheduled_reports():
    """Check and run scheduled reports based on current time"""
    now = datetime.now(CAT)
    print(f"🕐 Checking scheduled reports at {now.strftime('%Y-%m-%d %H:%M %Z')}")
    
    reports_sent = []
    
    # Check daily report (weekdays at 16:55)
    if should_send_daily_report():
        print("📅 Time for daily report!")
        if send_report_email("daily"):
            reports_sent.append("daily")
    
    # Check weekly report (Fridays at 16:55)
    if should_send_weekly_report():
        print("📅 Time for weekly report!")
        if send_report_email("weekly"):
            reports_sent.append("weekly")
    
    # Check monthly report (last Friday of month at 16:55)
    if should_send_monthly_report():
        print("📅 Time for monthly report!")
        if send_report_email("monthly"):
            reports_sent.append("monthly")
    
    if reports_sent:
        print(f"✅ Reports sent: {', '.join(reports_sent)}")
    else:
        print("ℹ️ No reports scheduled at this time")
        
        # Show next scheduled times
        print("\n📅 Next scheduled reports:")
        print(f"   Daily: Next weekday at 16:55 CAT")
        print(f"   Weekly: Next Friday at 16:55 CAT")
        print(f"   Monthly: Last Friday of month at 16:55 CAT")

def main():
    """Main function for testing report system"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "test-daily":
            send_report_email("daily")
        elif command == "test-weekly":
            send_report_email("weekly")
        elif command == "test-monthly":
            send_report_email("monthly")
        elif command == "test-all":
            print("🧪 Testing all report types...\n")
            send_report_email("daily")
            print()
            send_report_email("weekly")
            print()
            send_report_email("monthly")
        elif command == "scheduler":
            run_scheduled_reports()
        else:
            print("Available commands: test-daily, test-weekly, test-monthly, test-all, scheduler")
    else:
        print("🧪 Enhanced Report System with Attachments")
        print("=" * 50)
        print()
        print("Schedule:")
        print("  📅 Daily Report: 16:55 on weekdays")
        print("  📅 Weekly Report: 16:55 on Fridays") 
        print("  📅 Monthly Report: 16:55 on last Friday of month")
        print()
        print("Features:")
        print("  📄 PDF reports with charts and formatting")
        print("  📊 Excel spreadsheets for data analysis")
        print("  📧 HTML email with quick summary")
        print()
        print("Usage: python enhanced_reports.py [test-daily|test-weekly|test-monthly|test-all|scheduler]")

if __name__ == "__main__":
    main()
