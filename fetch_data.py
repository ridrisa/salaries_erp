from flask import Blueprint, Flask, request, jsonify, render_template
from google.cloud import bigquery
from google.oauth2 import service_account

fetch_data_bp = Blueprint('fetch_data', __name__)

# Configuration
PROJECT_ID = "looker-barqdata-2030"
KEY_PATH = "iamsmarter.json"

def get_bigquery_client():
    try:
        scopes = ["https://www.googleapis.com/auth/cloud-platform", "https://www.googleapis.com/auth/drive"]
        credentials = service_account.Credentials.from_service_account_file(KEY_PATH, scopes=scopes)
        client = bigquery.Client(credentials=credentials, project=PROJECT_ID)
        return client
    except Exception as e:
        print(f"Error configuring Google Cloud: {e}")
        return None

# Functions for fetching data
def fetch_tables(client, dataset_id):
    try:
        tables = client.list_tables(dataset_id)
        return [table.table_id for table in tables]
    except Exception as e:
        print(f"Error fetching tables: {e}")
        return []

def fetch_columns(client, dataset_id, table_id):
    try:
        table_ref = client.dataset(dataset_id).table(table_id)
        table = client.get_table(table_ref)
        return [field.name for field in table.schema]
    except Exception as e:
        print(f"Error fetching columns: {e}")
        return []

def execute_query(client, query):
    try:
        query_job = client.query(query)
        return list(query_job.result())
    except Exception as e:
        print(f"Error executing query: {e}")
        return []

# Functions for performance data
def fetch_performance_data(client, time_frame):
    if time_frame == 'day':
        query = """
        SELECT
            DATE_TRUNC(saudi_date, DAY) as date,
            COUNT(DID) as order_count,
            COUNT(DISTINCT(driver_username)) as drivers_count,
            SUM(PRICE) as revenue_amount,
            SUM(AMOUNT) as cod_collected,
            SUM(DRIVER_DEBIT_AMOUNT) as total_debits,
            SUM(DRIVER_CREDIT_AMOUNT) as total_credits
        FROM master_saned.jahez
        GROUP BY date
        ORDER BY date
        """
    elif time_frame == 'week':
        query = """
        SELECT
            DATE_TRUNC(saudi_date, WEEK) as date,
            COUNT(DID) as order_count,
            COUNT(DISTINCT(driver_username)) as drivers_count,
            SUM(PRICE) as revenue_amount,
            SUM(AMOUNT) as cod_collected,
            SUM(DRIVER_DEBIT_AMOUNT) as total_debits,
            SUM(DRIVER_CREDIT_AMOUNT) as total_credits
        FROM master_saned.jahez
        GROUP BY date
        ORDER BY date
        """
    elif time_frame == 'month':
        query = """
        SELECT
            DATE_TRUNC(saudi_date, MONTH) as date,
            COUNT(DID) as order_count,
            COUNT(DISTINCT(driver_username)) as drivers_count,
            SUM(PRICE) as revenue_amount,
            SUM(AMOUNT) as cod_collected,
            SUM(DRIVER_DEBIT_AMOUNT) as total_debits,
            SUM(DRIVER_CREDIT_AMOUNT) as total_credits
        FROM master_saned.jahez
        GROUP BY date
        ORDER BY date
        """
    else:
        raise ValueError("Invalid time frame")

    return execute_query(client, query)

# Functions for vehicle logs
def insert_vehicle_log(client, data):
    query = f"""
    INSERT INTO master_saned.vehicle_logs (Date, Rent_Type, Cars_Plate_Letter_English, Car_Plate_Numbers, Car_Plate, Car_Model, Movement_Type, Courier_ID_IQAMA_Number)
    VALUES ('{data['date']}', '{data['rent_type']}', '{data['cars_plate_letter_english']}', '{data['car_plate_numbers']}', '{data['car_plate']}', '{data['car_model']}', '{data['movement_type']}', '{data['courier_id']}')
    """
    return execute_query(client, query)

def update_vehicle_log(client, data):
    query = f"""
    UPDATE master_saned.vehicle_logs
    SET Rent_Type = '{data['rent_type']}', Cars_Plate_Letter_English = '{data['cars_plate_letter_english']}', Car_Plate_Numbers = '{data['car_plate_numbers']}', Car_Plate = '{data['car_plate']}', Car_Model = '{data['car_model']}', Movement_Type = '{data['movement_type']}', Courier_ID_IQAMA_Number = '{data['courier_id']}'
    WHERE Date = '{data['date']}'
    """
    return execute_query(client, query)

def delete_vehicle_log(client, date):
    query = f"DELETE FROM master_saned.vehicle_logs WHERE Date = '{date}'"
    return execute_query(client, query)

def fetch_vehicle_logs(client):
    query = "SELECT * FROM master_saned.vehicle_logs"
    return execute_query(client, query)

def fetch_vehicle_charts(client, time_frame):
    query = f"""
    SELECT DATE_TRUNC(Date, {time_frame}) as period, COUNT(Car_Plate_Numbers) as vehicle_count
    FROM master_saned.vehicle_logs
    GROUP BY period
    ORDER BY period
    """
    return execute_query(client, query)

def fetch_vehicle_insights(client, start_date, end_date):
    query = f"""
    SELECT Movement_Type, COUNT(*) as count
    FROM master_saned.vehicle_logs
    WHERE Date BETWEEN '{start_date}' AND '{end_date}'
    GROUP BY Movement_Type
    ORDER BY count DESC
    """
    return execute_query(client, query)

# Flask routes
@fetch_data_bp.route('/')
def index():
    return render_template('fetch_data.html')

@fetch_data_bp.route('/get_tables', methods=['GET'])
def get_tables():
    client = get_bigquery_client()
    if client:
        try:
            tables = client.list_tables("master_saned")
            table_names = [table.table_id for table in tables]
            return jsonify(tables=table_names)
        except Exception as e:
            return jsonify(error=str(e)), 500
    else:
        return jsonify(error="Failed to get BigQuery client"), 500

@fetch_data_bp.route('/get_columns', methods=['GET'])
def get_columns():
    table_name = request.args.get('table')
    if not table_name:
        return jsonify(error="Table name is required"), 400

    client = get_bigquery_client()
    if client:
        try:
            table_ref = client.dataset("master_saned").table(table_name)
            table = client.get_table(table_ref)
            column_names = [field.name for field in table.schema]
            return jsonify(columns=column_names)
        except Exception as e:
            return jsonify(error=str(e)), 500
    else:
        return jsonify(error="Failed to get BigQuery client"), 500

@fetch_data_bp.route('/execute_query', methods=['POST'])
def execute_query_route():
    data = request.json
    sql_query = data.get('sqlQuery')

    if not sql_query:
        return jsonify(error="SQL query is missing"), 400

    client = get_bigquery_client()
    if client:
        try:
            results = execute_query(client, sql_query)
            serialized_results = [dict(row) for row in results]  # Convert each row to a dictionary

            return jsonify(message=f"Query executed successfully. Fetched {len(results)} rows.", results=serialized_results)
        except Exception as e:
            return jsonify(error="An error occurred while executing the query."), 500
    else:
        return jsonify(error="Failed to get BigQuery client"), 500

# Function to create app (if needed)
def create_app():
    app = Flask(__name__)
    app.register_blueprint(fetch_data_bp, url_prefix='/fetch_data')
    return app
