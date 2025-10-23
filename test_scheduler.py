#!/usr/bin/env python3
"""
Simple scheduler for testing email notifications and daily reports
"""

import os
import sys
import time
from datetime import datetime, timedelta, timezone

# Add current directory to path so we can import core
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import our email functions (avoiding Flask dependencies)
from test_email import send_email, test_email_system, CAT, TEST_EMAIL

def test_booking_confirmation_email():
    """Test booking confirmation email"""
    try:
        print("🧪 Testing booking confirmation email...")
        
        # Sample booking data
        booking_data = {
            'id': 123,
            'client_name': 'John Smith',
            'room_name': 'Conference Room A',
            'start_time': '2025-07-24 09:00',
            'end_time': '2025-07-24 12:00',
            'purpose': 'Team Meeting',
            'status': 'confirmed',
            'notes': 'Please prepare projector and whiteboard'
        }
        
        subject = f"Booking Confirmation #{booking_data['id']} - {booking_data['room_name']}"
        
        # Generate HTML content
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .booking-details {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .footer {{ background-color: #f1f1f1; padding: 10px; text-align: center; font-size: 12px; }}
                .status-confirmed {{ color: #4CAF50; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎉 Booking Confirmed!</h1>
            </div>
            
            <div class="content">
                <p>Dear {booking_data['client_name']},</p>
                
                <p>Your booking has been <span class="status-confirmed">CONFIRMED</span>! Here are the details:</p>
                
                <div class="booking-details">
                    <h3>📋 Booking Details</h3>
                    <p><strong>Booking ID:</strong> #{booking_data['id']}</p>
                    <p><strong>Client:</strong> {booking_data['client_name']}</p>
                    <p><strong>Room/Venue:</strong> {booking_data['room_name']}</p>
                    <p><strong>Start:</strong> {booking_data['start_time']}</p>
                    <p><strong>End:</strong> {booking_data['end_time']}</p>
                    <p><strong>Purpose:</strong> {booking_data['purpose']}</p>
                    <p><strong>Status:</strong> <span class="status-confirmed">Confirmed</span></p>
                    <p><strong>Notes:</strong> {booking_data['notes']}</p>
                </div>
                
                <p>If you need to make any changes or have questions, please contact us immediately.</p>
                
                <p>Thank you for choosing our venue!</p>
            </div>
            
            <div class="footer">
                <p>This is an automated message. Please do not reply to this email.</p>
                <p>Generated on {datetime.now(CAT).strftime('%Y-%m-%d at %H:%M %Z')}</p>
            </div>
        </body>
        </html>
        """
        
        # Plain text version
        text_body = f"""
Booking Confirmed!

Dear {booking_data['client_name']},

Your booking has been CONFIRMED! Here are the details:

Booking ID: #{booking_data['id']}
Client: {booking_data['client_name']}
Room/Venue: {booking_data['room_name']}
Start: {booking_data['start_time']}
End: {booking_data['end_time']}
Purpose: {booking_data['purpose']}
Status: Confirmed
Notes: {booking_data['notes']}

If you need to make any changes or have questions, please contact us immediately.

Thank you for choosing our venue!

This is an automated message.
Generated on {datetime.now(CAT).strftime('%Y-%m-%d at %H:%M %Z')}
        """
        
        success = send_email(TEST_EMAIL, subject, html_body, text_body)
        
        if success:
            print("✅ Booking confirmation email test sent successfully!")
            return True
        else:
            print("❌ Failed to send booking confirmation email test")
            return False
            
    except Exception as e:
        print(f"❌ Error testing booking confirmation email: {str(e)}")
        return False

def test_daily_report_email():
    """Test daily report email"""
    try:
        print("🧪 Testing daily report email...")
        
        today = datetime.now(CAT).strftime('%Y-%m-%d')
        
        # Sample report data
        report_data = {
            'total_bookings': 5,
            'confirmed_bookings': 3,
            'tentative_bookings': 2,
            'cancelled_bookings': 0,
            'today_bookings': [
                {
                    'id': 101,
                    'client_name': 'ABC Company',
                    'room_name': 'Conference Room A',
                    'start_time': '2025-07-24 09:00',
                    'end_time': '2025-07-24 12:00',
                    'purpose': 'Board Meeting',
                    'status': 'confirmed'
                },
                {
                    'id': 102,
                    'client_name': 'XYZ Corp',
                    'room_name': 'Meeting Room B',
                    'start_time': '2025-07-24 14:00',
                    'end_time': '2025-07-24 16:00',
                    'purpose': 'Team Sync',
                    'status': 'tentative'
                }
            ],
            'tomorrow_bookings': [
                {
                    'id': 103,
                    'client_name': 'Tech Startup',
                    'room_name': 'Conference Room A',
                    'start_time': '2025-07-25 10:00',
                    'end_time': '2025-07-25 11:30',
                    'purpose': 'Investor Pitch',
                    'status': 'confirmed'
                }
            ]
        }
        
        subject = f"Daily Booking Report - {today}"
        
        # Generate HTML content
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
                .bookings-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                .bookings-table th, .bookings-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .bookings-table th {{ background-color: #f2f2f2; }}
                .status-confirmed {{ color: #4CAF50; font-weight: bold; }}
                .status-tentative {{ color: #FF9800; font-weight: bold; }}
                .footer {{ background-color: #f1f1f1; padding: 10px; text-align: center; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 Daily Booking Report</h1>
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
                
                <h3>📅 Today's Bookings</h3>
                <table class="bookings-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Client</th>
                            <th>Room</th>
                            <th>Start Time</th>
                            <th>End Time</th>
                            <th>Purpose</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for booking in report_data['today_bookings']:
            status_class = f"status-{booking['status']}"
            html_body += f"""
                        <tr>
                            <td>#{booking['id']}</td>
                            <td>{booking['client_name']}</td>
                            <td>{booking['room_name']}</td>
                            <td>{booking['start_time']}</td>
                            <td>{booking['end_time']}</td>
                            <td>{booking['purpose']}</td>
                            <td><span class="{status_class}">{booking['status'].title()}</span></td>
                        </tr>
            """
        
        html_body += f"""
                    </tbody>
                </table>
                
                <h3>📈 Tomorrow's Bookings Preview</h3>
                <table class="bookings-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Client</th>
                            <th>Room</th>
                            <th>Start Time</th>
                            <th>End Time</th>
                            <th>Purpose</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for booking in report_data['tomorrow_bookings']:
            status_class = f"status-{booking['status']}"
            html_body += f"""
                        <tr>
                            <td>#{booking['id']}</td>
                            <td>{booking['client_name']}</td>
                            <td>{booking['room_name']}</td>
                            <td>{booking['start_time']}</td>
                            <td>{booking['end_time']}</td>
                            <td>{booking['purpose']}</td>
                            <td><span class="{status_class}">{booking['status'].title()}</span></td>
                        </tr>
            """
        
        html_body += f"""
                    </tbody>
                </table>
            </div>
            
            <div class="footer">
                <p>Daily report generated automatically at 5:00 PM CAT</p>
                <p>Generated on {datetime.now(CAT).strftime('%Y-%m-%d at %H:%M %Z')}</p>
            </div>
        </body>
        </html>
        """
        
        # Plain text version
        text_body = f"""
Daily Booking Report - {today}

Statistics:
- Total Bookings: {report_data['total_bookings']}
- Confirmed: {report_data['confirmed_bookings']}
- Tentative: {report_data['tentative_bookings']}
- Cancelled: {report_data['cancelled_bookings']}

Today's Bookings: {len(report_data['today_bookings'])} bookings
Tomorrow's Bookings: {len(report_data['tomorrow_bookings'])} bookings

Report generated automatically at 5:00 PM CAT
Generated on {datetime.now(CAT).strftime('%Y-%m-%d at %H:%M %Z')}
        """
        
        success = send_email(TEST_EMAIL, subject, html_body, text_body)
        
        if success:
            print("✅ Daily report email test sent successfully!")
            return True
        else:
            print("❌ Failed to send daily report email test")
            return False
            
    except Exception as e:
        print(f"❌ Error testing daily report email: {str(e)}")
        return False

def main():
    """Main function to run email tests"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "test-basic":
            test_email_system()
        elif command == "test-booking":
            test_booking_confirmation_email()
        elif command == "test-report":
            test_daily_report_email()
        elif command == "test-all":
            print("🧪 Running all email tests...\n")
            
            print("1️⃣ Testing basic email system...")
            basic_success = test_email_system()
            print()
            
            if basic_success:
                print("2️⃣ Testing booking confirmation email...")
                booking_success = test_booking_confirmation_email()
                print()
                
                print("3️⃣ Testing daily report email...")
                report_success = test_daily_report_email()
                print()
                
                if booking_success and report_success:
                    print("✅ All email tests completed successfully!")
                else:
                    print("⚠️ Some email tests failed. Check the output above.")
            else:
                print("❌ Basic email test failed. Please configure email credentials first.")
        else:
            print("Available commands: test-basic, test-booking, test-report, test-all")
    else:
        print("🧪 Email Testing Script")
        print("Usage: python test_scheduler.py [test-basic|test-booking|test-report|test-all]")
        print()
        print("Commands:")
        print("  test-basic   - Test basic email configuration")
        print("  test-booking - Test booking confirmation email")
        print("  test-report  - Test daily report email")
        print("  test-all     - Run all email tests")

if __name__ == "__main__":
    main()
