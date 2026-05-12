# main.py
import app
import utime

# Short delay to allow boot messages to be printed before the app starts
utime.sleep_ms(500)

if __name__ == "__main__":
    app.run_app()