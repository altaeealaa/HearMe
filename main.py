from handlers.handlers_call import create_bot
from database.database_setup import setup_database  # Import setup function

if __name__ == "__main__":
    setup_database()  # Create tables if they don't exist
    app = create_bot()
    app.run_polling()
