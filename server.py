from __future__ import annotations

import json
import os
import re
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Ensure waste_management_agent package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from waste_management_agent.agent import (
    FACILITIES,
    PICKUP_SCHEDULE,
    SERVICE_REQUESTS,
    WASTE_CATEGORIES,
    get_disposal_guidelines,
    get_facility_info,
    get_pickup_schedule,
    get_service_request_info,
)

PORT = 8000


def process_user_chat(message: str) -> str:
    """Process user message using tools and dataset grounding."""
    msg_lower = message.lower().strip()

    # 1. Check schedule queries
    if any(k in msg_lower for k in ["schedule", "pickup", "when is", "collection", "trash day", "zone"]):
        zone_match = re.search(r"zone\s*([a-e])", msg_lower)
        if zone_match:
            zone_letter = zone_match.group(1).upper()
            zone_map = {
                "A": "Zone A - North",
                "B": "Zone B - South",
                "C": "Zone C - East",
                "D": "Zone D - West",
                "E": "Zone E - Central",
            }
            zone_name = zone_map.get(zone_letter, "Zone A - North")

            waste_type = None
            if "organic" in msg_lower or "food" in msg_lower:
                waste_type = "Organic"
            elif "recycl" in msg_lower or "paper" in msg_lower or "cardboard" in msg_lower:
                waste_type = "Recyclables"
            elif "hazard" in msg_lower:
                waste_type = "Hazardous"
            elif "general" in msg_lower or "black bin" in msg_lower or "trash" in msg_lower:
                waste_type = "General Waste"

            res = get_pickup_schedule(zone=zone_name, waste_type=waste_type)
            if res["status"] == "success":
                lines = [f"### 🚚 Waste Collection Schedule for **{zone_name}**\n"]
                for item in res["schedules"]:
                    lines.append(f"• **{item['waste_type']}** (`{item['bin_color']}`): {', '.join(item['days'])} between {item['time_window']}.")
                    lines.append(f"  *Instructions:* {item['instructions']}\n")
                return "\n".join(lines)

        return "Could you please specify your municipal zone? (e.g. **Zone A - North**, **Zone B - South**, **Zone C - East**, **Zone D - West**, or **Zone E - Central**)."

    # 2. Check sorting / disposal guidelines
    if any(k in msg_lower for k in ["sort", "recycle", "dispose", "how to", "where to put", "battery", "batteries", "paint", "e-waste", "electronics", "glass", "plastic", "paper", "cardboard", "organic", "medical", "sharps", "furniture", "couch", "mattress"]):
        category = None
        if any(k in msg_lower for k in ["e-waste", "electronic", "laptop", "phone", "tv", "appliance", "computer"]):
            category = "E-Waste & Electronics"
        elif any(k in msg_lower for k in ["paint", "chemical", "hazard", "battery", "batteries", "oil", "cleaner"]):
            category = "Hazardous Waste"
        elif any(k in msg_lower for k in ["food", "compost", "organic", "yard", "peel", "scrap"]):
            category = "Organic Waste"
        elif any(k in msg_lower for k in ["plastic", "can", "bottle", "packaging"]):
            category = "Plastics & Packaging"
        elif any(k in msg_lower for k in ["paper", "cardboard", "box", "envelope"]):
            category = "Paper & Cardboard"
        elif any(k in msg_lower for k in ["glass", "jar"]):
            category = "Glass"
        elif any(k in msg_lower for k in ["couch", "mattress", "furniture", "bulky", "table"]):
            category = "Bulky Items"
        elif any(k in msg_lower for k in ["needle", "syringe", "medical", "sharp", "medicine"]):
            category = "Medical Waste"

        if category:
            res = get_disposal_guidelines(category=category)
            if res["status"] == "success":
                g = res["guidelines"]
                lines = [
                    f"### ♻️ Disposal Guidelines for **{category}**\n",
                    f"• **Designated Bin / Container**: `{g['bin_color']}`",
                    f"• **Acceptable Items**: {', '.join(g['acceptable_items'])}",
                    f"• **Unacceptable Items**: {', '.join(g['unacceptable_items'])}",
                    f"• **Preparation**: {g['preparation']}",
                    f"• **Disposal Method**: {g['disposal_method']}",
                ]
                return "\n".join(lines)
        else:
            res = get_disposal_guidelines()
            cats = "\n".join([f"• **{c}**" for c in res["categories"]])
            return f"Here are the waste categories available for sorting guidelines:\n\n{cats}\n\nWhich item or category would you like help sorting?"

    # 3. Check facility info
    if any(k in msg_lower for k in ["facility", "center", "depot", "location", "address", "hours", "open"]):
        fac_type = None
        if "recycle" in msg_lower or "recycling" in msg_lower:
            fac_type = "Recycling Center"
        elif "compost" in msg_lower:
            fac_type = "Composting Facility"
        elif "e-waste" in msg_lower or "battery" in msg_lower or "tech" in msg_lower:
            fac_type = "E-Waste Hub"
        elif "transfer" in msg_lower or "debris" in msg_lower:
            fac_type = "Transfer Station"
        elif "hazard" in msg_lower or "eco depot" in msg_lower or "chemical" in msg_lower:
            fac_type = "Hazardous Drop-off"
        elif "office" in msg_lower or "headquarters" in msg_lower or "admin" in msg_lower:
            fac_type = "Main Administrative Office"

        if fac_type:
            res = get_facility_info(facility_type=fac_type)
            if res["status"] == "success":
                info = res["info"]
                lines = [
                    f"### 📍 **{info['name']}** ({fac_type})\n",
                    f"• **Address**: {info['address']}",
                    f"• **Weekday Hours**: {info['weekday_hours']}",
                    f"• **Weekend Hours**: {info['weekend_hours']}",
                    f"• **Accepted Items**: {info['accepted_items']}",
                    f"• **Fees / Incentives**: {info['incentives_or_fees']}",
                    f"• **Contact**: {info['contact']}",
                ]
                return "\n".join(lines)
        else:
            return "We have several municipal facilities: **Recycling Center**, **Composting Facility**, **E-Waste Hub**, **Transfer Station**, **Hazardous Drop-off**, and **Main Administrative Office**. Which one would you like details for?"

    # 4. Check service requests
    if any(k in msg_lower for k in ["bulk", "request", "book", "extra bin", "stolen", "broken", "dumping", "replacement"]):
        srv_type = None
        if "bulk" in msg_lower or "furniture" in msg_lower:
            srv_type = "Bulk Pickup"
        elif "extra bin" in msg_lower or "additional bin" in msg_lower:
            srv_type = "Extra Bin Request"
        elif "hazard" in msg_lower:
            srv_type = "Hazardous Disposal"
        elif "dumping" in msg_lower or "fly-tipping" in msg_lower or "illegal" in msg_lower:
            srv_type = "Illegal Dumping Report"
        elif "replacement" in msg_lower or "broken" in msg_lower or "stolen" in msg_lower:
            srv_type = "Bin Replacement"

        if srv_type:
            res = get_service_request_info(service_type=srv_type)
            if res["status"] == "success":
                info = res["info"]
                lines = [
                    f"### 📋 **{info['service']}**\n",
                    f"• **Description**: {info['description']}",
                    f"• **Lead Time**: {info['lead_time']}",
                    f"• **Fee Structure**: {info['fee']}",
                    f"• **Steps to Book**:",
                ]
                for idx, step in enumerate(info["procedure"], 1):
                    lines.append(f"  {idx}. {step}")
                lines.append(f"• **Contact**: {info['contact']}")
                return "\n".join(lines)

    # General greeting fallback
    return (
        "Hello! I am your **Municipal Waste Management Assistant** 🌿.\n\n"
        "I can help you with:\n"
        "• 🚚 **Collection Schedules**: Ask about pickup days in Zone A, B, C, D, or E.\n"
        "• ♻️ **Sorting Guidelines**: Ask how to dispose of batteries, food waste, plastics, e-waste, etc.\n"
        "• 📍 **Drop-off Facilities**: Find operating hours and locations for recycling centers & eco depots.\n"
        "• 📋 **Service Requests**: Learn how to book bulky item pickups or request extra bins."
    )


class CustomHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {
                "schedules": PICKUP_SCHEDULE,
                "categories": WASTE_CATEGORIES,
                "facilities": FACILITIES,
                "services": SERVICE_REQUESTS,
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/chat":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                payload = json.loads(body.decode("utf-8"))
                user_msg = payload.get("message", "")
                reply = process_user_chat(user_msg)
                response_data = {"reply": reply, "status": "success"}
            except Exception as e:
                response_data = {"reply": f"Error: {str(e)}", "status": "error"}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
            return

        self.send_error(404, "Endpoint Not Found")


def run_server():
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, CustomHandler)
    print(f"Server starting on http://localhost:{PORT} ...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    run_server()
