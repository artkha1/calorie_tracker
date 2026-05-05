from ui.ui import app

if __name__ == "__main__":
    # use_reloader=False avoids Windows watchdog restarting the server when unrelated
    # files change (can cause ERR_CONNECTION_RESET right after login).
    app.run(debug=True, use_reloader=False)