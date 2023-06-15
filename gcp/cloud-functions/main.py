from google.cloud import bigquery
import json
from datetime import datetime


def fve_update(request):
    # Extract JSON data from the request
    request_json = request.get_json()

    # Verify that JSON data exists
    if not request_json:
        return "No data provided", 400

    # Create a BigQuery client
    client = bigquery.Client()

    # Define the BigQuery dataset and table
    dataset_id = "L0"
    table_id = "update"

    # Insert JSON data into BigQuery
    table_ref = client.dataset(dataset_id).table(table_id)
    table = client.get_table(table_ref)

    hass_name = request_json["hass_name"]
    hass_ip = request.remote_addr
    hass_location_lat = request_json["hass_location_lat"]
    hass_location_lon = request_json["hass_location_lon"]
    hass_id = f"{hass_name}::{hass_location_lat}:{hass_location_lon}"
    data = request_json["data"]

    rows_to_insert = [
        {
            "hass_id": hass_id,
            "hass_name": hass_name,
            "hass_ip": _get_ip(request),
            "hass_location": {
                "latitude": hass_location_lat,
                "longitude": hass_location_lon,
            },
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": json.dumps(data)
        }
    ]
    errors = client.insert_rows(table, rows_to_insert)

    if errors == []:
        return "OK"
    else:
        return f"Error inserting data into BigQuery: {errors}", 500


def fve_decisions(request):
    # Extract JSON data from the request
    request_json = request.get_json()

    # Verify that JSON data exists
    if not request_json:
        return "No data provided", 400

    # Create a BigQuery client
    client = bigquery.Client()

    # Define the BigQuery dataset and table
    dataset_id = "L0"
    table_id = "decisions"

    # Insert JSON data into BigQuery
    table_ref = client.dataset(dataset_id).table(table_id)
    table = client.get_table(table_ref)

    hass_name = request_json["hass_name"]
    hass_ip = request.remote_addr
    hass_location_lat = request_json["hass_location_lat"]
    hass_location_lon = request_json["hass_location_lon"]
    hass_id = f"{hass_name}::{hass_location_lat}:{hass_location_lon}"
    decisions = request_json["data"]
    decisions_load = []
    for d in decisions:
        decisions_load.append(json.dumps(d))


    rows_to_insert = [
        {
            "hass_id": hass_id,
            "hass_name": hass_name,
            "hass_ip": _get_ip(request),
            "hass_location": {
                "latitude": hass_location_lat,
                "longitude": hass_location_lon,
            },
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": decisions_load
        }
    ]
    errors = client.insert_rows(table, rows_to_insert)

    if errors == []:
        return "OK"
    else:
        return f"Error inserting data into BigQuery: {errors}", 500


def _get_ip(request):
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        return request.environ['REMOTE_ADDR']
    else:
        return request.environ['HTTP_X_FORWARDED_FOR']