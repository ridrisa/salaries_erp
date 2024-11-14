import json
import cloudscraper
from flask import Blueprint, request, jsonify, session, current_app
from flask_login import login_required

saned_bp = Blueprint('saned_bp', __name__)

headers = {
    "Accept": "application/json, */*; q=0.01",
    "Referer": "https://saned.io/driver/driverDashboard.jsp",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
}

def saned_login_helper(scraper, username, password):
    login_url = "https://saned.io/Login"
    login_data = {"username": "barqkhadamatftacc", "password": "20@30Barq"}
    response = scraper.post(login_url, data=login_data, headers=headers)
    
    current_app.logger.debug("Login response status: %s", response.status_code)
    current_app.logger.debug("Login response content: %s", response.content)
    
    if response.headers.get('Content-Type') == 'text/html':
        current_app.logger.debug("Received HTML response, likely an error page")
        return None
    
    try:
        response_text = response.text
        if response_text.startswith("0|"):
            response_text = response_text[2:]

        response_json = json.loads(response_text)
        current_app.logger.debug(f"Parsed login JSON response: {response_json}")

        if response.status_code == 200 and "token" in response_json:
            session["saned_cookies"] = scraper.cookies.get_dict()
            session["saned_token"] = response_json["token"]
            return scraper.cookies
    except json.JSONDecodeError as e:
        current_app.logger.error("JSON decode error: %s", str(e))
        current_app.logger.error("Response content: %s", response.content)
    except Exception as e:
        current_app.logger.error("An error occurred: %s", str(e))
        current_app.logger.error("Response content: %s", response.content)

    return None

def ensure_login():
    payload = {"password": "20@30Barq", "username": "barqkhadamatftacc"}
    scraper = cloudscraper.create_scraper()
    response = saned_login_helper(scraper, payload["username"], payload["password"])

    if response is None:
        return None

    return response

@saned_bp.route("/login_to_saned", methods=["POST"])
@login_required
def login_to_saned():
    cookies = ensure_login()
    if cookies:
        return jsonify(success=True)
    else:
        return jsonify(success=False, error="Login failed. Please check the logs for more details.")

@saned_bp.route("/update_imei", methods=["POST"])
@login_required
def update_imei():
    cookies = ensure_login()
    if not cookies:
        return jsonify(success=False, error="Login to Saned failed")

    data = request.json
    driver_id = data.get("driverId")
    new_imei = data.get("newImei")
    update_url = "https://saned.io/updateDriverImei"
    payload = {"id": driver_id, "newImei": new_imei}
    scraper = cloudscraper.create_scraper()
    scraper.cookies.update(cookies)
    response = scraper.post(update_url, data=payload, headers=headers)
    
    response_text = response.text
    current_app.logger.debug(f"Update IMEI response status: {response.status_code}")
    current_app.logger.debug(f"Update IMEI response content: {response_text}")

    if response_text.startswith("0|"):
        response_text = response_text[2:]

    try:
        response_json = json.loads(response_text)
        current_app.logger.debug(f"Parsed JSON response: {response_json}")

        if response.status_code == 200 and 'response' in response_json and response_json['response'] == "IMEI updated":
            return jsonify(success=True, message="IMEI updated successfully")
        else:
            current_app.logger.debug(f"Unexpected response format: {response_json}")
            return jsonify(success=False, error="Unexpected response format or error occurred")
    except json.JSONDecodeError:
        current_app.logger.error(f"Failed to decode JSON response: {response_text}")
        return jsonify(success=False, error="Failed to decode response from Saned API")


@saned_bp.route("/activate_driver", methods=["POST"])
@login_required
def activate_driver():
    cookies = ensure_login()
    if not cookies:
        return jsonify(success=False, error="Login to Saned failed")

    data = request.json
    driver_id = data.get("driverId")
    activate_url = "https://saned.io/activateDriver"
    payload = {"driverId": driver_id}
    scraper = cloudscraper.create_scraper()
    scraper.cookies.update(cookies)
    response = scraper.post(activate_url, data=payload, headers=headers)
    
    response_text = response.text
    current_app.logger.debug(f"Activate driver response status: {response.status_code}")
    current_app.logger.debug(f"Activate driver response content: {response_text}")

    return jsonify(success=(response.status_code == 200), message=response_text)

@saned_bp.route("/deactivate_driver", methods=["POST"])
@login_required
def deactivate_driver():
    cookies = ensure_login()
    if not cookies:
        return jsonify(success=False, error="Login to Saned failed")

    data = request.json
    driver_id = data.get("driverId")
    deactivate_url = "https://saned.io/deactivateDriver"
    payload = {"driverId": driver_id}
    scraper = cloudscraper.create_scraper()
    scraper.cookies.update(cookies)
    response = scraper.post(deactivate_url, data=payload, headers=headers)
    
    response_text = response.text
    current_app.logger.debug(f"Deactivate driver response status: {response.status_code}")
    current_app.logger.debug(f"Deactivate driver response content: {response_text}")

    return jsonify(success=(response.status_code == 200), message=response_text)

@saned_bp.route("/reset_password", methods=["POST"])
@login_required
def reset_password():
    cookies = ensure_login()
    if not cookies:
        return jsonify(success=False, error="Login to Saned failed")

    data = request.json
    driver_id = data.get("driverId")
    imei = data.get("imei")
    new_password = data.get("newPassword")
    reset_url = "https://saned.io/resetDriverPassword"
    payload = {"id": driver_id, "imei": imei, "password": new_password}
    scraper = cloudscraper.create_scraper()
    scraper.cookies.update(cookies)
    response = scraper.post(reset_url, data=payload, headers=headers)
    
    response_text = response.text
    current_app.logger.debug(f"Reset password response status: {response.status_code}")
    current_app.logger.debug(f"Reset password response content: {response_text}")

    if response_text.startswith("0|"):
        response_text = response_text[2:]

    return jsonify(success=(response.status_code == 200), message=response_text)


@saned_bp.route("/add_priority", methods=["POST"])
@login_required
def add_priority():
    cookies = ensure_login()
    if not cookies:
        return jsonify(success=False, error="Login to Saned failed")

    data = request.json
    driver_id = data.get("driverId")
    tag_id = data.get("tagId")
    tag_priority = data.get("tagPriority")
    priority_url = "https://saned.io/saveDriverTags"
    payload = {"driverId": driver_id, "tagId": tag_id, "tagPriority": tag_priority}
    scraper = cloudscraper.create_scraper()
    scraper.cookies.update(cookies)
    response = scraper.post(priority_url, data=payload, headers=headers)
    
    response_text = response.text
    current_app.logger.debug(f"Add priority response status: {response.status_code}")
    current_app.logger.debug(f"Add priority response content: {response_text}")

    if response_text.startswith("0|"):
        response_text = response_text[2:]

    return jsonify(success=(response.status_code == 200), message=response_text)


@saned_bp.route("/delete_driver_tags", methods=["POST"])
@login_required
def delete_driver_tags():
    cookies = ensure_login()
    if not cookies:
        return jsonify(success=False, error="Login to Saned failed")

    data = request.json
    driver_id = data.get("driverId")
    tag_id = data.get("tagId")
    delete_url = "https://saned.io/deleteDriverTags"
    payload = {"driverId": driver_id, "tagId": tag_id}
    scraper = cloudscraper.create_scraper()
    scraper.cookies.update(cookies)
    response = scraper.post(delete_url, data=payload, headers=headers)
    
    response_text = response.text
    current_app.logger.debug(f"Delete driver tags response status: {response.status_code}")
    current_app.logger.debug(f"Delete driver tags response content: {response_text}")

    if response_text.startswith("0|"):
        response_text = response_text[2:]

    return jsonify(success=(response.status_code == 200), message=response_text)


@saned_bp.route("/update_mobile", methods=["POST"])
@login_required
def update_mobile():
    cookies = ensure_login()
    if not cookies:
        return jsonify(success=False, error="Login to Saned failed")

    data = request.json
    driver_id = data.get("driverId")
    new_mobile = data.get("newMobile")
    update_mobile_url = "https://saned.io/updateMobile"
    payload = {"driverId": driver_id, "mobile": new_mobile}
    scraper = cloudscraper.create_scraper()
    scraper.cookies.update(cookies)
    response = scraper.post(update_mobile_url, data=payload, headers=headers)
    
    response_text = response.text
    current_app.logger.debug(f"Update mobile response status: {response.status_code}")
    current_app.logger.debug(f"Update mobile response content: {response_text}")

    if response_text.startswith("0|"):
        response_text = response_text[2:]

    return jsonify(success=(response.status_code == 200), message=response_text)



