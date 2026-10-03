# Web Budget Tracker

A modern, user-friendly web application for tracking personal expenses and managing budgets. Built with Flask and deployed on Vercel, featuring Google OAuth authentication, smart spending insights, and a responsive dark/light theme interface.

## Features

- **Google OAuth Login**: Secure authentication using Google accounts
- **Budget Management**: Set monthly, weekly, or daily budgets with savings goals
- **Expense Tracking**: Add, edit, and delete expenses with categories
- **Smart Insights**: AI-powered spending personality analysis based on patterns
- **History & Archiving**: Automatic period resets with historical data snapshots
- **Responsive Design**: Modern UI with dark/light theme toggle
- **Real-time Updates**: Live budget progress and remaining balance calculations

## Tech Stack

- **Backend**: Python Flask
- **Frontend**: HTML5, CSS3, JavaScript
- **Authentication**: Google OAuth 2.0 (Flask-Dance)
- **Deployment**: Vercel (serverless)
- **Data Storage**: JSON file (local/demo) - migrate to database for production

## Installation & Local Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jpnj05/Web-Budget-Tracker.git
   cd Web-Budget-Tracker
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   - Create a `.env` file in the root directory
   - Add your Google OAuth and Supabase credentials:
     ```
     SECRET_KEY=your-flask-secret-key
     GOOGLE_CLIENT_ID=your-google-client-id
     GOOGLE_CLIENT_SECRET=your-google-client-secret
     SUPABASE_URL=https://your-project.supabase.co
     SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
     ```
   - Do not commit `.env` to GitHub.

5. **Run the application**:
   ```bash
   python app.py
   ```
   - Open http://localhost:5000 in your browser

## Deployment on Vercel

The app is configured for easy deployment on Vercel:

1. **Connect to Vercel**:
   - Import this GitHub repository to Vercel
   - Vercel will auto-detect the Python configuration

2. **Set Environment Variables** in Vercel dashboard:
   - `SECRET_KEY`
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`

3. **Deploy**: Vercel handles the build and deployment automatically

**Important**: This app now uses Supabase for storage, so you must create the database tables before the app will work.

## Supabase setup

1. In Supabase, open the SQL editor.
2. Run the SQL in `supabase_schema.sql`.
3. Confirm that `users`, `expenses`, and `history` tables exist.

## Usage

1. **Login**: Authenticate with your Google account
2. **Set Budget**: Configure your budget amount, period, and savings goal
3. **Add Expenses**: Track purchases with names, amounts, and categories
4. **Monitor Progress**: View spending insights and personality analysis
5. **Review History**: Access archived periods and reapply past expenses

## Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google+ API
4. Create OAuth 2.0 credentials
5. Add authorized redirect URIs:
   - Local: `http://localhost:5000/google_login`
   - Vercel: `https://your-app.vercel.app/google_login`

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -m 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Open a Pull Request

## License

This project is open source and available under the [MIT License](LICENSE).

## Screenshots

<img width="939" height="944" alt="Screenshot 2026-10-03 141832" src="https://github.com/user-attachments/assets/fa5a53cf-5776-44cc-af14-8b95fbe52694" />

---

<img width="992" height="952" alt="image" src="https://github.com/user-attachments/assets/5d4ac18c-f484-41b4-bb0e-6613a5f57eb4" />




## Live Demo



---

Built with ❤️ using Flask and modern web technologies.
