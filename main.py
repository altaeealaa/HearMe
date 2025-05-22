from handlers.handlers_call import create_bot


if __name__ == "__main__":
    app = create_bot()
    app.run_polling()

 