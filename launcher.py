"""
Supermarket App Launcher
========================
This script is bundled by PyInstaller into a standalone .exe.
It starts the Streamlit server and opens the browser automatically.
"""
import subprocess
import sys
import os
import webbrowser
import threading
import time
import socket


def get_local_ip():
    """Get the machine's local network IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def open_browser(port):
    """Wait a moment then open the browser."""
    time.sleep(4)
    webbrowser.open(f"http://localhost:{port}")


def main():
    PORT = 8501

    # Determine base paths depending on whether running as .exe or .py
    if getattr(sys, "frozen", False):
        # Running inside PyInstaller bundle
        base_dir = sys._MEIPASS          # bundled files (app.py, etc.)
        work_dir = os.path.dirname(sys.executable)  # where the .exe lives (for the DB)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        work_dir = base_dir

    app_py = os.path.join(base_dir, "app.py")

    # The database lives next to the .exe so it persists between runs
    os.chdir(work_dir)

    local_ip = get_local_ip()

    print("=" * 55)
    print("  🛒  SUPERMARKET APP")
    print("=" * 55)
    print(f"  Local (this PC):    http://localhost:{PORT}")
    print(f"  Network (phones):   http://{local_ip}:{PORT}")
    print()
    print("  Share the Network URL with phones on the same WiFi.")
    print("  Press Ctrl+C to stop the server.")
    print("=" * 55)

    # Open browser automatically
    threading.Thread(target=open_browser, args=(PORT,), daemon=True).start()

    # Build the Streamlit command
    streamlit_cmd = [
        sys.executable, "-m", "streamlit", "run", app_py,
        "--server.port", str(PORT),
        "--server.address", "0.0.0.0",       # accessible on local network
        "--server.headless", "true",           # no 'do you want to send analytics' prompt
        "--browser.gatherUsageStats", "false",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "false",
    ]

    try:
        subprocess.run(streamlit_cmd, check=True)
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except subprocess.CalledProcessError as e:
        print(f"\nError starting server: {e}")
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
