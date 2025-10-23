# Rainbow Towers Conference Room Booking System

Professional conference room booking and management system built with Flask and Supabase.

## Features

- 📅 **Advanced Calendar System** - Today, Weekly, and Monthly views with drag-and-drop
- 🎨 **Rainbow Towers Branding** - Professional design with gold color scheme
- 💰 **Quotation & Invoice Generation** - Automated PDF generation with branding
- 👥 **Client Management** - Track organizations and contacts
- 🏢 **Room Management** - Multiple venues with capacity tracking
- 📊 **Comprehensive Reports** - Revenue, utilization, and activity analytics
- 🔐 **User Authentication** - Secure login with role-based access
- 🌍 **CAT Timezone** - Full support for Central Africa Time (UTC+2)

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: Supabase (PostgreSQL)
- **Frontend**: HTML, CSS, JavaScript
- **PDF Generation**: html2pdf.js
- **Authentication**: Flask-Login
- **Calendar**: FullCalendar.js

## Setup Instructions

### Prerequisites

- Python 3.11 or higher
- Supabase account
- Git

### Installation

1. **Clone the repository**:

```bash
git clone https://github.com/JT-ZW/conference-room-booking-system.git
cd conference-room-booking-system
```

2. **Create virtual environment**:

```bash
python -m venv venv
```

3. **Activate virtual environment**:

```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

4. **Install dependencies**:

```bash
pip install -r requirements.txt
```

5. **Configure environment variables**:

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your credentials
```

Required environment variables:

```
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_supabase_service_key
SECRET_KEY=your_secret_key_here
```

6. **Run the application**:

```bash
python app.py
```

Visit `http://localhost:5000` in your browser.

## Database Setup

The application uses Supabase (PostgreSQL). Required tables:

- `users` - User accounts
- `clients` - Client/organization information
- `rooms` - Conference rooms/venues
- `bookings` - Booking records
- `booking_custom_addons` - Add-ons for bookings
- `event_types` - Event categories
- `addon_categories` - Add-on categories
- `addons` - Available add-ons/services
- `user_activity_log` - Activity tracking
- `auth_activity_log` - Authentication logs

## Deployment

### Recommended Platform: Render.com

1. Push your code to GitHub
2. Create a new Web Service on Render
3. Connect your GitHub repository
4. Set environment variables in Render dashboard
5. Deploy!

See deployment guides in `/docs` folder (if available).

## Project Structure

```
conference-room-booking-system/
├── app.py                 # Main application file
├── requirements.txt       # Python dependencies
├── Procfile              # Deployment configuration
├── .env.example          # Environment variables template
├── routes/               # Application routes
├── settings/             # Configuration files
├── static/               # CSS, JavaScript, images
├── templates/            # HTML templates
├── utils/                # Helper functions
└── README.md            # This file
```

## Features in Detail

### Calendar Views

- **Today View**: Airport-style board showing today's bookings
- **Weekly View**: Grid view with room availability across the week
- **Monthly View**: FullCalendar integration with month overview

### Quotation System

- Professional PDF generation with Rainbow Towers branding
- Line item breakdown for services and add-ons
- Currency selection (USD/ZWG)
- Automatic filename generation

### Reporting

- Revenue analytics
- Room utilization statistics
- Client analysis
- Daily/Weekly/Monthly summaries

## Contributing

This is a private project for Rainbow Towers. For internal contributions, please follow the company's development guidelines.

## License

Proprietary - Rainbow Towers Conference Center

## Support

For support, contact the IT department at Rainbow Towers.

---

Built with ❤️ for Rainbow Towers Conference Center
