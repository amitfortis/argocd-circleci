from flask import (
    Blueprint,
    render_template,
    request,
    Response,
    jsonify,
    abort,
    send_file,
    current_app,
)
from .weatherclass import *
from boto3 import client, resource
from prometheus_flask_exporter import PrometheusMetrics
from datetime import datetime
import uuid
import time
import ecs_logging
import logging
import json
import os

HISTORY_DIR = "/app/search_history"

# logging.basicConfig(
#    filename="/var/log/flask/app.log",
#    level=logging.DEBUG,
#    format="%(asctime)s %(levelname)s: %(message)s",
# )


bp = Blueprint("pages", __name__)
metrics = PrometheusMetrics(bp)

metrics.info("app_info", "Application info", version="1.0.3")

logger = logging.getLogger("app")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler("/var/log/flask/logs.json")
handler.setFormatter(ecs_logging.StdlibFormatter())
logger.addHandler(handler)


def save_search_history(location, weather_data):
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)

    filename = f"{location.replace(' ', '_')}.json"
    filepath = os.path.join(HISTORY_DIR, filename)

    new_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "weather_data": [day.__dict__ for day in weather_data.days],
    }

    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            file_content = f.read()
            if file_content:
                existing_data = json.loads(file_content)
            else:
                existing_data = {"location": location, "searches": []}
    else:
        existing_data = {"location": location, "searches": []}

    existing_data["searches"].append(new_data)

    with open(filepath, "w") as f:
        json.dump(existing_data, f, indent=2, default=str)


@bp.route("/history")
def history():
    if not os.path.exists(HISTORY_DIR):
        return render_template("pages/history.html", history_data=[])

    files = [f for f in os.listdir(HISTORY_DIR) if f.endswith(".json")]
    history_data = []
    for file in files:
        location = file.rsplit(".", 1)[0].replace("_", " ")
        history_data.append({"location": location, "file": file})

    # Sort history_data by location
    history_data.sort(key=lambda x: x["location"])

    return render_template("pages/history.html", history_data=history_data)


@bp.route("/download/<filename>")
def download_file(filename):
    return send_file(os.path.join(HISTORY_DIR, filename), as_attachment=True)


def get_s3_client():
    return client("s3", "eu-central-1")


def get_dynamodb_resource():
    return resource("dynamodb", region_name="eu-central-1")


@bp.route("/sky", methods=["GET"])
def index():
    logger.info("Download image request received")
    try:
        s3 = get_s3_client()
        file = s3.get_object(Bucket="mybucket-amit", Key="sky.jpg")
        return Response(
            file["Body"].read(),
            headers={"Content-Disposition": "attachment;filename=sky.jpg"},
        )
    except Exception as e:
        logger.error(f"Error retrieving image from S3: {e}")
        abort(500)


@bp.route("/", methods=["POST", "GET"])
@metrics.do_not_track()
@metrics.counter(
    "invocation_by_location",
    "Number of invocations by location",
    labels={
        "location": lambda: request.form["content"]
        if request.method == "POST"
        else None
    },
)
def home():
    if request.method == "POST":
        content = request.form["content"]
        if not content:
            abort(400)
        else:
            weather_data = WeatherData(content)
            save_search_history(content, weather_data)
            return render_template("pages/results.html", days=weather_data.days)
    return render_template("pages/home.html")


@bp.route("/upload", methods=["POST"])
def upload_to_dynamodb():
    logger.info("DynamoDB data insertion request received")
    try:
        data = request.json
        location = data.get("location")
        weather_data = data.get("weatherData")
        if not location or not weather_data:
            return jsonify({"message": "No location or weather data provided"}), 400

        dynamodb = get_dynamodb_resource()
        table = dynamodb.Table("weather-data")

        try:
            table.put_item(
                Item={
                    "id": str(uuid.uuid4()),
                    "timestamp": int(time.time()),
                    "location": location,
                    "weather_data": weather_data,
                }
            )
            logger.info("Data successfully saved to DynamoDB")
            return jsonify(
                {
                    "message": f"Successfully uploaded weather data for {location} to DynamoDB"
                }
            ), 200
        except Exception as e:
            logger.error(
                f"Error uploading weather data for {location} to DyanmoDB: {e}"
            )
            print(f"Error uploading to DynamoDB: {str(e)}")
            return jsonify(
                {"message": f"Failed to upload weather data for {location} to DynamoDB"}
            ), 500
    except Exception as e:
        logger.error(f"Failed to insert data: {e}")


@bp.route("/tlv", methods=["GET"])
def fetch_and_upload_tlv_weather():
    logger.info("Backup request for Tel Aviv received")
    try:
        # Fetch weather data for Tel Aviv using WeatherData class
        weather_data = WeatherData("Tel Aviv")

        # Prepare data for upload
        location = str(weather_data.location)
        formatted_data = []

        for day in weather_data.days:
            date = str(day.date)
            formatted_data.append(f"{date}:Daytime Temperature:{day.day_temperature}")
            formatted_data.append(
                f"{date}:Nighttime Temperature:{day.night_temperature}"
            )
            formatted_data.append(f"{date}:Daytime Humidity:{day.day_humidity}")
            formatted_data.append(f"{date}:Nighttime Humidity:{day.night_humidity}")

        # Upload to DynamoDB
        dynamodb = get_dynamodb_resource()
        table = dynamodb.Table("tlv-weather")  # Use your actual table name

        # Create a single item with all weather data
        item = {
            "id": str(uuid.uuid4()),
            "timestamp": int(time.time()),
            "location": location,
            "weather_data": formatted_data,
        }

        # Upload the item to DynamoDB
        table.put_item(Item=item)
        logger.info("Backup data successfully saved to DynamoDB")
        return jsonify(
            {
                "message": "Successfully fetched and uploaded weather data for Tel Aviv",
                "location": location,
                "weatherData": formatted_data,
            }
        ), 200

    except Exception as e:
        print(f"Error fetching or uploading data: {str(e)}")
        logger.error(f"Error during backup: {e}")
        return jsonify(
            {"message": "Failed to fetch and upload weather data for Tel Aviv"}
        ), 500


@bp.errorhandler(400)
def location_not_found(e):
    logger.error("Error Location not found")
    return render_template("pages/400.html"), 400


@bp.errorhandler(500)
def api_bad_request(e):
    logger.error("Error API Bad Request")
    return render_template("pages/500.html"), 500
