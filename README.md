# UniTrade

UniTrade is a campus-only marketplace for University of Windsor students to buy and sell items.

## Tech Stack

- Django (Python)
- Django Templates + Bootstrap 5
- SQLite for development (PostgreSQL compatible)

## Setup

1. Create a virtual environment:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Run migrations:
   - `python manage.py migrate`
4. Load sample data:
   - `python manage.py loaddata initial_data.json`
5. Start the server:
   - `python manage.py runserver`

## Demo Accounts

- Username: `demo_user`
- Password: `password123`

## Key Features

- User authentication with password reset
- Item listings with multiple images
- Search, filters, and pagination
- Messaging between buyers and sellers
- User dashboard with recently viewed items

## Notes

- Password reset emails are sent to the console in development.
- Uploaded images are stored in the `media/` folder.
