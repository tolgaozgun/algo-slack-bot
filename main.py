import os
import time
import requests
from bs4 import BeautifulSoup
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from threading import Thread

# UPS Tracking URL
UPS_TRACKING_URL = "https://www.ups.com/track?track=yes&trackNums=1ZA03R690337671312&loc=en_US&requester=ST/trackdetails"

# Environment variables for Slack
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#general")  # Default channel if not set

# Initialize Slack app
app = App(token=SLACK_BOT_TOKEN)

# Global variable to store last status
last_status = None

def fetch_ups_status():
    """Fetch the latest status from the UPS tracking page."""
    try:
        response = requests.get(UPS_TRACKING_URL, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # Extract the tracking status - update the selector if necessary
            status_element = soup.find("div", class_="latest-status")
            if status_element:
                return status_element.text.strip()
        return None
    except Exception as e:
        print(f"Error fetching UPS status: {e}")
        return None

def track_package():
    """Background task to check UPS tracking status every hour."""
    global last_status
    while True:
        new_status = fetch_ups_status()
        if new_status and new_status != last_status:
            last_status = new_status
            message = f"📦 *UPS Tracking Update:* {new_status}\n🔗 {UPS_TRACKING_URL}"
            app.client.chat_postMessage(channel=SLACK_CHANNEL, text=message)
        time.sleep(3600)  # Wait 1 hour

@app.command("/track")
def handle_track_command(ack, respond):
    """Handles the `/track` command."""
    ack()
    status = fetch_ups_status()
    if status:
        respond(f"📦 *Current UPS Tracking Status:* {status}\n🔗 {UPS_TRACKING_URL}")
    else:
        respond("⚠️ Could not retrieve tracking information at this time.")

# Start tracking in a separate thread
Thread(target=track_package, daemon=True).start()

# Start the bot
if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()