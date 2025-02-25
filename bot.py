import os
import time
import requests
import json
import logging
from threading import Thread
from flask import Flask, request, jsonify
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)

# UPS API Endpoint
UPS_TRACKING_URL = "https://webapis.ups.com/track/api/Track/GetStatus?loc=en_US"

HUMAN_READABLE_URL = "https://www.ups.com/track?track=yes&trackNums=1ZA03R690337671312&loc=en_US&requester=ST/trackdetails"

# Updated Headers
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "origin": "https://www.ups.com",
    "priority": "u=1, i",
    "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133")',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "x-xsrf-token": "CfDJ8Jcj9GhlwkdBikuRYzfhrpKAXoNi5j8s9t25w4ANNbIgblOalNSAXURCiml4Msavo4Q6IFZHu7JORCVgS_OHtvVK7a69vkNladh-yy4hSPo7_Uxk87gx2JfbWYdhn1EWdN6vyzmAF8bBIJatPFy3goo",
}

# Updated Cookies
COOKIES = {
    "sharedsession": "6b5e72c8-5c10-4d65-9a22-06cd7669b312:m",
    "X-CSRF-TOKEN": "CfDJ8Jcj9GhlwkdBikuRYzfhrpJGL-XIYUxBOM3KoU9n4J0J3OEhijI70KbxAOtF2YJ-hlomkXhX8JUb4YWAKN5N8txKXwObox02HM3qT7oShphnqCaE1voSHggF3GZG8whlxFZOqmrpduCaIQDMS8WHq4c",
    "PIM-SESSION-ID": "jCSE3iYaAHsnDHqR",
    "at_check": "true",
}

# Updated Request Payload
DATA = {
    "Locale": "en_US",
    "TrackingNumber": ["1ZA03R690337671312"],
    "isBarcodeScanned": False,
    "Requester": "st/trackdetails",
    "returnToValue": "",
}


# Slack Bot Tokens
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_BOT_SIGNING_SECRET")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#general")  # Default Slack channel

# Initialize Slack App
slack_app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)

# Initialize Flask App
app = Flask(__name__)
handler = SlackRequestHandler(slack_app)

# Stores last tracking status to avoid duplicate messages
last_status = None

def fetch_ups_status():
    """Fetch the latest UPS tracking status from the API and parse the response."""
    try:
        response = requests.post(
            UPS_TRACKING_URL, headers=HEADERS, cookies=COOKIES, json=DATA, timeout=30
        )

        if response.status_code == 200:
            result = response.json()

            # Ensure response contains tracking details
            if "trackDetails" in result and len(result["trackDetails"]) > 0:
                track_info = result["trackDetails"][0]

                # Extract general package status
                package_status = track_info.get("packageStatus", "Unknown Status")

                # Extract latest tracking update
                shipment_progress = track_info.get("shipmentProgressActivities", [])
                if shipment_progress:
                    latest_update = shipment_progress[0]  # First entry is the most recent
                    status_description = latest_update.get("activityScan", "No recent update.")
                    event_location = latest_update.get("location", "Unknown Location")
                    event_date = latest_update.get("date", "Unknown Date")
                    event_time = latest_update.get("time", "Unknown Time")

                    status_message = (
                        f"📦 *UPS Tracking Update:* {package_status}\n"
                        f"📅 *Latest Update:* {status_description}\n"
                        f"📍 *Location:* {event_location}\n"
                        f"🕒 *Date & Time:* {event_date} {event_time}\n"
                        f"🔗 Track Package: {HUMAN_READABLE_URL}"
                    )
                else:
                    status_message = f"📦 *UPS Tracking Update:* {package_status}\n🔗 Track Package: {HUMAN_READABLE_URL}"

                return status_message

            return "⚠️ No tracking details available at the moment."

        return f"⚠️ Error: UPS API returned status {response.status_code}"

    except requests.exceptions.Timeout:
        print("Error: UPS request timed out. Retrying in next cycle...")
        return "⚠️ UPS API request timed out. Please try again later."
    except requests.exceptions.RequestException as e:
        print(f"Error fetching UPS status: {e}")
        return "⚠️ Failed to fetch UPS tracking status."


def track_package():
    """Check UPS tracking status every hour and send updates to Slack."""
    global last_status
    while True:
        new_status = fetch_ups_status()
        if new_status and new_status != last_status:
            last_status = new_status
            slack_app.client.chat_postMessage(channel=SLACK_CHANNEL, text=new_status)
        time.sleep(3600)  # Check every hour


@slack_app.event("message")
def handle_message_events(event, say):
    """Respond when a user sends a message in the channel."""
    text = event.get("text", "").lower()
    print("text", text)

    if "hoodie" in text:
        say(fetch_ups_status())


@app.route("/slack/track", methods=["POST"])
def slack_track_command():
    """Handles the /track slash command from Slack."""
    data = request.form
    user_id = data.get("user_id")
    response_url = data.get("response_url")

    tracking_status = fetch_ups_status()

    # Send an immediate acknowledgment
    return jsonify({
        "response_type": "in_channel",
        "text": f"📦 *UPS Tracking Status for <@{user_id}>:*\n{tracking_status}"
    })


# Start tracking in a separate thread
Thread(target=track_package, daemon=True).start()

# Start Flask App
if __name__ == "__main__":
    print("Bot is running")
    app.run(host="0.0.0.0", port=3000)  # Listens on all interfaces
