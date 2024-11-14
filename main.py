from flask import Flask, session, redirect, url_for, request, jsonify, render_template, send_file, make_response
from flask_session import Session
from authlib.integrations.flask_client import OAuth
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin
import os
import logging
from google.cloud import bigquery, storage, exceptions
import io
import csv
import math
from saned import saned_bp  # Import the Blueprint
import pdfkit
import sys
import calendar
from datetime import datetime
from fetch_data import fetch_data_bp  # Import the Blueprint
from fetch_data import get_bigquery_client, execute_query, fetch_tables, fetch_columns, fetch_performance_data, fetch_vehicle_charts, fetch_vehicle_insights, fetch_vehicle_logs, insert_vehicle_log, update_vehicle_log, delete_vehicle_log

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Ensure a secure secret key for session management

session_dir = "./sys"
try:
    if not os.path.exists(session_dir):
        os.makedirs(session_dir, mode=0o700, exist_ok=True)
except OSError as e:    
    sys.exit(1)


# Session configuration
app.config["SESSION_TYPE"] = 'filesystem'
app.config["SESSION_FILE_DIR"] = session_dir
Session(app)

# Import logging and set up the logger
from logging.handlers import RotatingFileHandler

# Set up a specific logger with our desired output level
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add the log message handler to the logger
handler = RotatingFileHandler('sys/app.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.DEBUG)

# Create a console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Add formatter
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')
handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to the logger
logger.addHandler(handler)
logger.addHandler(console_handler)

# Apply the logger to the app
app.logger.addHandler(handler)
app.logger.addHandler(console_handler)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "iamsmarter.json"

# Set your Google Cloud project ID
project_id = "looker-barqdata-2030"

# Google Cloud setup
client = get_bigquery_client()
if not client:
    raise SystemExit("Failed to initialize Google Cloud BigQuery client")

storage_client = storage.Client(project_id)

# OAuth setup using Authlib
oauth = OAuth(app)
login_manager = LoginManager()
login_manager.init_app(app)  # Initialize the LoginManager with the app
login_manager.login_view = "login"

google = oauth.register(
    "google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),                           
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    authorize_params=None,
    access_token_url="https://oauth2.googleapis.com/token",
    access_token_params=None,
    refresh_token_url=None,
    client_kwargs={"scope": "openid email profile"},
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration"
)

class User(UserMixin):
    def __init__(self, id, email):
        self.id = id
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    return User(user_id, session.get("email"))

@app.before_request
def preload_couriers():
    if 'couriers' not in session:
        try:
            query = "SELECT DISTINCT Name FROM master_saned.courier"
            results = execute_query(client, query)
            couriers = [row["Name"] for row in results]
            session['couriers'] = couriers
            app.logger.debug(f"Couriers preloaded: {couriers}")
        except exceptions.Forbidden as e:
            app.logger.error(f"Permission Denied: {e}")
        except Exception as e:
            app.logger.error(f"An error occurred while preloading couriers: {e}")

def fetch_distinct_values(column):
    query = f"SELECT DISTINCT {column} FROM master_saned.ultimate"
    results = execute_query(client, query)
    return [row[column] for row in results]

@app.route("/login")
def login():
    redirect_uri = url_for("authorized", _external=True)
    state = os.urandom(24).hex()
    nonce = os.urandom(24).hex()
    session['state'] = state
    session['nonce'] = nonce
    return oauth.google.authorize_redirect(redirect_uri, state=state, nonce=nonce)

@app.route("/login/authorized")
def authorized():
    state = session.pop('state', None)
    received_state = request.args.get('state')
    if not state or received_state != state:
        return "Error: Invalid state parameter", 400
    token = oauth.google.authorize_access_token()
    userinfo = oauth.google.parse_id_token(token, nonce=session.pop('nonce', None))
    session["email"] = userinfo.get("email")
    user = User(id=userinfo.get("sub"), email=userinfo.get("email"))
    login_user(user)
    return redirect(url_for("index"))

@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("index"))

@app.route('/get_scorecards_data')
@login_required
def get_scorecards_data():
    data = {
        "total_active_couriers": fetch_metric("select count(distinct(BARQ_ID)) from master_saned.courier where Status = 'Active'"),
        "active_ecommerce_couriers": fetch_metric("select count(distinct(BARQ_ID)) from master_saned.courier where Status = 'Active' and Project = 'Ecommerce'"),
        "active_food_couriers": fetch_metric("select count(distinct(BARQ_ID)) from master_saned.courier where Status = 'Active' and Project = 'Food'"),
        "active_motorcycle_couriers": fetch_metric("select count(distinct(BARQ_ID)) from master_saned.courier where Status = 'Active' and Project = 'Motorcycle'"),
        "inhouse_couriers": fetch_metric("select count(distinct(BARQ_ID)) from master_saned.courier where Status = 'Active' and Sponsorshipstatus = 'Inhouse'"),
        "ajeer_couriers": fetch_metric("select count(distinct(BARQ_ID)) from master_saned.courier where Status = 'Active' and Sponsorshipstatus = 'Ajeer'")
    }
    return jsonify(data)

@app.route('/get_all_couriers')
@login_required
def get_all_couriers():
    try:
        query = "SELECT * FROM master_saned.courier"
        results = execute_query(client, query)
        couriers = [dict(row) for row in results]
        return jsonify({'couriers': couriers})
    except Exception as e:
        app.logger.error(f"Error fetching all couriers: {e}")
        return jsonify(error="An error occurred while fetching all couriers."), 500

@app.route('/get_total_active_couriers')
@login_required
def get_total_active_couriers():
    count = fetch_metric("SELECT COUNT(DISTINCT(BARQ_ID)) FROM master_saned.courier WHERE Status = 'Active'")
    return jsonify({"count": count})

@app.route('/get_active_ecommerce_couriers')
@login_required
def get_active_ecommerce_couriers():
    count = fetch_metric("SELECT COUNT(DISTINCT(BARQ_ID)) FROM master_saned.courier WHERE Status = 'Active' AND Project = 'Ecommerce'")
    return jsonify({"count": count})

@app.route('/holistic')
@login_required
def holistic():
    app.logger.debug("holistic page accessed")
    try:
        return render_template('holistic.html')
    except Exception as e:
        app.logger.error(f"Error rendering index.html: {e}")
        return "Error rendering page", 500

@app.route('/get_active_food_couriers')
@login_required
def get_active_food_couriers():
    count = fetch_metric("SELECT COUNT(DISTINCT(BARQ_ID)) FROM master_saned.courier WHERE Status = 'Active' AND Project = 'Food'")
    return jsonify({"count": count})

@app.route('/get_active_motorcycle_couriers')
@login_required
def get_active_motorcycle_couriers():
    count = fetch_metric("SELECT COUNT(DISTINCT(BARQ_ID)) FROM master_saned.courier WHERE Status = 'Active' AND Project = 'Motorcycle'")
    return jsonify({"count": count})

@app.route('/get_inhouse_couriers')
@login_required
def get_inhouse_couriers():
    count = fetch_metric("SELECT COUNT(DISTINCT(BARQ_ID)) FROM master_saned.courier WHERE Status = 'Active' AND Sponsorshipstatus = 'Inhouse'")
    return jsonify({"count": count})

@app.route('/get_ajeer_couriers')
@login_required
def get_ajeer_couriers():
    count = fetch_metric("SELECT COUNT(DISTINCT(BARQ_ID)) FROM master_saned.courier WHERE Status = 'Active' AND Sponsorshipstatus = 'Ajeer'")
    return jsonify({"count": count})

def fetch_metric(query):
    client = get_bigquery_client()
    results = execute_query(client, query)
    return results[0][0] if results else 0

@app.route("/")
@login_required
def index():
    app.logger.debug("Index page accessed")
    try:
        return render_template("index.html")
    except Exception as e:
        app.logger.error(f"Error rendering index.html: {e}")
        return "Error rendering page", 500

@app.route("/saned_management")
@login_required
def saned_management():
    app.logger.debug("Saned management page accessed")
    try:
        return render_template("super.html")
    except Exception as e:
        app.logger.error(f"Error rendering saned.html: {e}")
        return "Error rendering page", 500

@app.route('/saned/performance_data')
@login_required
def performance_data():
    time_frame = request.args.get('time_frame', 'day')
    try:
        data = fetch_performance_data(client, time_frame)
        response_data = {
            'dates': [row['date'] for row in data],
            'order_count': [row['order_count'] for row in data],
            'drivers_count': [row['drivers_count'] for row in data],
            'revenue_amount': [row['revenue_amount'] for row in data],
            'cod_collected': [row['cod_collected'] for row in data],
            'total_debits': [row['total_debits'] for row in data],
            'total_credits': [row['total_credits'] for row in data]
        }
        return jsonify(response_data)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

# NEW ROUTE: fetch_distinct_values
@app.route('/fetch_distinct_values', methods=['GET'])
@login_required
def fetch_distinct_values_route():
    try:
        sponsorship_query = "SELECT DISTINCT Sponsorshipstatus FROM master_saned.ultimate"
        project_query = "SELECT DISTINCT PROJECT FROM master_saned.ultimate"
        status_query = "SELECT DISTINCT Status FROM master_saned.ultimate"

        sponsorship_results = execute_query(client, sponsorship_query)
        project_results = execute_query(client, project_query)
        status_results = execute_query(client, status_query)

        sponsorship_status = [
            row['Sponsorshipstatus'] for row in sponsorship_results
        ]
        projects = [row['PROJECT'] for row in project_results]
        statuses = [row['Status'] for row in status_results]

        return jsonify({
            'sponsorshipStatus': sponsorship_status,
            'project': projects,
            'status': statuses,
        })
    except Exception as e:
        app.logger.error(f"Error fetching distinct values: {e}")
        return jsonify(
            error="An error occurred while fetching distinct values."), 500

# MODIFIED ROUTE: fetch_data
@app.route('/fetch_data', methods=['GET', 'POST'])
@login_required
def fetch_data():
    if request.method == 'GET':
        tables = fetch_tables(client, "master_saned")
        return render_template('fetch_data.html', tables=tables)
    else:
        data = request.json
        sql_query = data.get('sqlQuery')

        if not sql_query:
            return jsonify(error="SQL query is missing"), 400

        try:
            results = execute_query(client, sql_query)
            serialized_results = [dict(row) for row in results]  # Convert each row to a dictionary

            session['last_query'] = {
                'sql_query': sql_query
            }
            return jsonify(message=f"Query executed successfully. Fetched {len(results)} rows.", results=serialized_results)
        except Exception as e:
            app.logger.error(f"Error executing export data query: {e}")
            return jsonify(error="An error occurred while executing the query."), 500

# NEW ROUTE: download_csv
@app.route('/download_csv')
@login_required
def download_csv():
    last_query = session.get('last_query')
    if not last_query:
        return "No query to download", 400

    sql_query = last_query['sql_query']
    if not sql_query:
        return "Query is missing", 400

    try:
        results = execute_query(client, sql_query)

        si = io.StringIO()
        cw = csv.writer(si)
        if results:
            cw.writerow(results[0].keys())
            for row in results:
                cw.writerow(row.values())

        output = io.BytesIO()
        output.write(si.getvalue().encode('utf-8'))
        output.seek(0)

        return send_file(output,
                         mimetype='text/csv',
                         as_attachment=True,
                         download_name='results.csv')
    except Exception as e:
        app.logger.error(f"Error downloading CSV: {e}")
        return str(e), 500

@app.route('/export_data', methods=['POST'])
@login_required
def export_data():
    app.logger.debug("Export data request received")
    data = request.json
    sql_query = data.get('sqlQuery')

    if not sql_query:
        return jsonify(error="SQL query is missing"), 400

    try:
        results = execute_query(client, sql_query)
        return jsonify(
            message=f"Query executed successfully. Fetched {len(results)} rows."
        )
    except Exception as e:
        app.logger.error(f"Error executing export data query: {e}")
        return jsonify(
            error="An error occurred while executing the query."), 500

@app.route('/fetch_columns', methods=['POST'])
@login_required
def fetch_columns_route():
    table = request.json.get('table')
    if table:
        columns = fetch_columns(client, "master_saned", table)
        return jsonify(columns=columns)
    return jsonify(error="Table not specified"), 400

@app.route('/fetch_data_query', methods=['POST'])
@login_required
def fetch_data_query():
    selected_table = request.form.get('table')
    selected_columns = request.form.getlist('columns')
    limit = request.form.get('limit')
    if selected_table and selected_columns:
        try:
            columns = ', '.join(selected_columns)
            query = f"SELECT {columns} FROM master_saned.{selected_table}"
            if limit.isdigit():
                query += f" LIMIT {limit}"
            elif limit.upper() == "ALL":
                query = f"SELECT {columns} FROM master_saned.{selected_table}"
            results = execute_query(client, query)

            session['last_query'] = {
                'table': selected_table,
                'columns': selected_columns,
                'limit': limit
            }

            tables = fetch_tables(client, "master_saned")
            return render_template('fetch_data.html',
                                   results=results,
                                   columns=selected_columns,
                                   tables=tables,
                                   selected_table=selected_table,
                                   limit=limit)
        except Exception as e:
            app.logger.error(f"Error executing query: {e}")
            return render_template('fetch_data.html', error=str(e))
    tables = fetch_tables(client, "master_saned")
    return render_template('fetch_data.html',
                           error="Please select a table and columns.",
                           tables=tables)

@app.route('/courier_profile')
@login_required
def courier_profile():
    app.logger.debug("Courier profile page accessed")
    try:
        couriers = session.get('couriers', [])
        joining_dates = fetch_distinct_values('Joining_Date')
        barq_ids = fetch_distinct_values('BARQ_ID')
        statuses = fetch_distinct_values('Status')
        id_numbers = fetch_distinct_values('ID_Number')
        sponsorships = fetch_distinct_values('Sponsorshipstatus')
        
        return render_template('courier_profile.html',
                               couriers=couriers,
                               joining_dates=joining_dates,
                               barq_ids=barq_ids,
                               statuses=statuses,
                               id_numbers=id_numbers,
                               sponsorships=sponsorships)
    except exceptions.Forbidden as e:
        app.logger.error(f"Permission Denied: {e}")
        return jsonify(
            error="Permission Denied. Please check the service account permissions."
        ), 403
    except Exception as e:
        app.logger.error(f"An error occurred: {e}")
        return jsonify(error="An error occurred. Please check the logs."), 500

@app.route('/get_courier_details', methods=['GET'])
@login_required
def get_courier_details():
    barq_id = request.args.get('barq_id')
    if not barq_id:
        return jsonify({"error": "BARQ ID is required"}), 400
    try:
        query = f"SELECT * FROM master_saned.courier WHERE BARQ_ID = {barq_id}"
        results = execute_query(client, query)
        if results:
            courier = dict(results[0])
            return jsonify({"courier": courier})
        else:
            return jsonify({"error": "Courier not found"}), 404
    except Exception as e:
        app.logger.error(f"Error fetching courier details: {e}")
        return jsonify(error="An error occurred while fetching courier details."), 500

@app.route('/get_courier_data', methods=['POST'])
@login_required
def get_courier_data():
    app.logger.debug("Get courier data accessed")
    try:
        courier_name = request.json.get('courier_name')
        filter_date = request.json.get('filter_date')
        filter_BARQ_ID = request.json.get('filter_BARQ_ID')
        filter_status = request.json.get('filter_status')
        filter_id_number = request.json.get('filter_id_number')
        filter_sponsorship = request.json.get('filter_sponsorship')

        query = "SELECT * FROM master_saned.courier WHERE 1=1"
        if courier_name:
            query += f" AND Name = '{courier_name}'"
        if filter_date:
            query += f" AND Joining_Date = '{filter_date}'"
        if filter_BARQ_ID:
            query += f" AND CAST(BARQ_ID AS STRING) = '{filter_BARQ_ID}'"
        if filter_status:
            query += f" AND Status = '{filter_status}'"
        if filter_id_number:
            query += f" AND CAST(ID_Number AS STRING)= '{filter_id_number}'"
        if filter_sponsorship:
            query += f" AND Sponsorshipstatus = '{filter_sponsorship}'"

        results = execute_query(client, query)
        courier_data = [dict(row) for row in results]
        return jsonify({'courier_data': courier_data})
    except exceptions.Forbidden as e:
        app.logger.error(f"Permission Denied: {e}")
        return jsonify(
            error="Permission Denied. Please check the service account permissions."
        ), 403
    except Exception as e:
        app.logger.error(f"An error occurred: {e}")
        return jsonify(error="An error occurred. Please check the logs."), 500

@app.route('/get_couriers_paginated', methods=['GET'])
@login_required
def get_couriers_paginated():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        offset = (page - 1) * per_page
        query = f"SELECT * FROM master_saned.courier LIMIT {per_page} OFFSET {offset}"
        results = execute_query(client, query)
        couriers = [dict(row) for row in results]
        total_count_query = "SELECT COUNT(*) as total FROM master_saned.courier"
        total_count_result = execute_query(client, total_count_query)
        total_count = total_count_result[0]['total']
        return jsonify({'couriers': couriers, 'total': total_count})
    except Exception as e:
        app.logger.error(f"Error fetching paginated couriers: {e}")
        return jsonify(error="An error occurred while fetching couriers."), 500

@app.route('/download_pdf')
@login_required
def download_pdf():
    app.logger.debug("Download PDF accessed")
    last_query = session.get('last_query')
    if not last_query:
        return "No query to download", 400

    selected_table = last_query['table']
    selected_columns = last_query['columns']
    limit = last_query['limit']

    if not selected_table or not selected_columns:
        return "Table and columns must be specified", 400

    try:
        columns = ', '.join(selected_columns)
        query = f"SELECT {columns} FROM master_saned.{selected_table}"
        if limit.isdigit():
            query += f" LIMIT {limit}"
        results = execute_query(client, query)

        html = render_template('results_template.html',
                               results=results,
                               columns=selected_columns)
        pdf = pdfkit.from_string(html, False)

        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers[
            'Content-Disposition'] = 'attachment; filename=results.pdf'

        return response
    except Exception as e:
        app.logger.error(f"Error downloading PDF: {e}")
        return str(e), 500

@app.route('/performance_orders')
@login_required
def performance_orders():
    app.logger.debug("Performance orders page accessed")
    try:
        return render_template('performance_orders.html')
    except Exception as e:
        app.logger.error(f"Error rendering performance_orders.html: {e}")
        return "Error rendering page", 500

@app.route('/calculate_salary', methods=['POST'])
def calculate_salary():
    try:
        data = request.get_json()
        category = data.get('category')
        month = data.get('month')
        year = data.get('year')
        custom_params = data.get('customParams', {})

        # Validate inputs
        if not all([category, month, year]):
            logging.warning("Missing required fields in the request.")
            return jsonify({"error": "Missing required fields"}), 400

        if category == "All":
            categories = [
                "Motorcycle", "Food Trial", "Food In-House New",
                "Food In-House Old", "Ecommerce WH", "Ecommerce"
            ]
        else:
            categories = [category]

        all_results = []
        for cat in categories:
            start_date, end_date = get_period(cat, int(month), int(year))
            query = generate_query(cat, start_date, end_date)
            try:
                query_job = client.query(query)
                results = [dict(row) for row in query_job.result()]
            except Exception as e:
                logging.error(f"BigQuery execution failed: {e}")
                return jsonify({"error": "Failed to execute query",
                                "details": str(e)}), 500

            if not results:
                logging.info(f"No results found for category {cat}.")
                continue

            processed_results = calculate_salary_details(
                results, cat, start_date, end_date,
                custom_params.get(cat, {})
            )
            all_results.extend(processed_results)

        if not all_results:
            return jsonify({"message": "No results found for the given query."
                            }), 404

        return jsonify({
            "data": all_results,
            "meta": {
                "categories": categories,
                "period": {
                    "month": month,
                    "year": year
                },
                "count": len(all_results)
            }
        })

    except Exception as e:
        logging.exception("Unexpected error during salary calculation.")
        return jsonify({"error": "Internal server error",
                        "details": str(e)}), 500

def get_period(category, month, year):
    """Calculate start and end dates based on category."""
    if category == "Ajeer":
        if month == 12:
            start_date = f"{year}-12-15"
            end_date = f"{year + 1}-01-14"
        else:
            start_date = f"{year}-{month:02d}-15"
            end_date = f"{year}-{(month % 12) + 1:02d}-14"
    else:
        if month == 1:
            start_date = f"{year - 1}-12-25"
            end_date = f"{year}-{month:02d}-24"
        else:
            start_date = f"{year}-{month - 1:02d}-25"
            end_date = f"{year}-{month:02d}-24"
    logging.debug(f"Period for category '{category}' from {start_date} "
                  f"to {end_date}.")
    return start_date, end_date

def generate_query(category, start_date, end_date):
    """Build BigQuery SQL based on category."""
    base_query = f"""
    WITH CurrentPeriod AS (
        SELECT DATE '{start_date}' AS StartPeriod,
               DATE '{end_date}' AS EndPeriod
    )
    SELECT 
        u.BARQ_ID,
        u.iban,
        u.id_number,
        FORMAT_DATE('%Y-%m-%d', u.joining_Date) AS joining_Date,
        u.Name,
        u.Status,
        u.Sponsorshipstatus,
        u.PROJECT,
        u.Supervisor,
        SUM(u.total_Orders) AS Total_Orders,
        SUM(u.Total_revenue) AS Total_Revenue,
        SUM(u.Gas_Usage_without_vat) AS Gas_Usage,"""

    category_queries = {
        "Motorcycle": {
            "target": "t.motorcycle AS TARGET",
            "condition": "WHERE u.PROJECT = 'Motorcycle'"
        },
        "Food Trial": {
            "target": "t.Food_Trial AS TARGET",
            "condition": ("WHERE u.PROJECT = 'Food' AND "
                          "u.Sponsorshipstatus = 'Trial'")
        },
        "Food In-House New": {
            "target": "t.Food_Inhouse AS TARGET",
            "condition": ("WHERE u.PROJECT = 'Food' AND "
                          "u.Sponsorshipstatus = 'Inhouse' AND "
                          "u.joining_Date >= '2024-01-01'")
        },
        "Food In-House Old": {
            "target": "t.Food_Inhouse AS TARGET",
            "condition": ("WHERE u.PROJECT = 'Food' AND "
                          "u.Sponsorshipstatus = 'Inhouse' AND "
                          "u.joining_Date < '2024-01-01'")
        },
        "Ecommerce WH": {
            "target": "t.Ecommerce_WH AS TARGET",
            "condition": "WHERE u.PROJECT = 'Ecommerce WH'"
        },
        "Ecommerce": {
            "target": "t.Ecommerce AS TARGET",
            "condition": "WHERE u.PROJECT = 'Ecommerce'"
        },
        "Ajeer": {
            "target": "t.Ajeer AS TARGET",
            "condition": "WHERE u.Sponsorshipstatus = 'Ajeer'"
        }
    }

    if category not in category_queries:
        logging.error(f"Invalid category provided: {category}")
        raise ValueError(f"Invalid category: {category}")

    query_parts = category_queries[category]

    query = f"""
    {base_query}
        {query_parts['target']}
    FROM master_saned.ultimate AS u
    LEFT JOIN master_saned.targets AS t 
        ON EXTRACT(DAY FROM DATE '{end_date}') = t.Day
    {query_parts['condition']}
    AND u.Date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
    GROUP BY 
        u.BARQ_ID,
        u.iban,
        u.id_number,
        u.joining_Date,
        u.Name,
        u.Status,
        u.Sponsorshipstatus,
        u.PROJECT,
        u.Supervisor,
        TARGET
    """
    logging.debug(f"Generated BigQuery:\n{query}")
    return query

def calculate_salary_details(results, category, start_date, end_date,
                             custom_params):
    """Calculate salary components based on category and query results."""
    processed = []

    for result in results:
        total_orders = result.get('Total_Orders', 0)
        target = result.get('TARGET', 0)
        gas_usage = result.get('Gas_Usage', 0)
        joining_date = result.get('joining_Date')
        total_revenue = result.get('Total_Revenue', 0)
        status = result.get('Status', '')

        # Calculate days since joining
        try:
            joining_date_obj = datetime.strptime(joining_date, '%Y-%m-%d')
            days_since_joining = (datetime.now() - joining_date_obj).days + 1
        except Exception as e:
            logging.error(f"Error processing joining date '{joining_date}': "
                          f"{e}")
            continue  # Skip this record if date processing fails

        # Initialize salary components
        salary_components = {
            "Basic_Salary": 0,
            "Bonus_Amount": 0,
            "Gas_Deserved": 0,
            "Gas_Difference": 0,
            "Total_Salary": 0
        }

        # Define calculation functions for each category
        calculation_functions = {
            "Motorcycle": calculate_motorcycle_salary,
            "Food Trial": calculate_food_trial_salary,
            "Food In-House New": calculate_food_inhouse_new_salary,
            "Food In-House Old": calculate_food_inhouse_old_salary,
            "Ecommerce WH": calculate_ecommerce_wh_salary,
            "Ecommerce": calculate_ecommerce_salary,
            "Ajeer": calculate_ajeer_salary
        }

        calc_func = calculation_functions.get(category)
        if calc_func:
            salary_components = calc_func(
                total_orders, target, gas_usage, days_since_joining,
                total_revenue, custom_params
            )
        else:
            logging.warning(f"No calculation function defined for category: "
                            f"{category}")
            continue  # Skip if no calculation function is defined

        # Update the result with calculated components
        result.update(salary_components)

        # Add period information
        result.update({
            "period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "days_since_joining": days_since_joining,
            "generated_date": datetime.now().strftime('%Y-%m-%d'),
            "category": category
        })

        processed.append(result)

    logging.info(f"Processed {len(processed)} salary records.")
    return processed

# Salary calculation functions for each category

def calculate_motorcycle_salary(total_orders, target, gas_usage,
                                days_since_joining, total_revenue, params):
    final_target = min(math.ceil(target), days_since_joining * 13.333)
    basic_salary_rate = params.get('motorcycle_basic_salary_rate', 53.33333)
    bonus_rate = params.get('motorcycle_bonus_rate', 6)
    penalty_rate = params.get('motorcycle_penalty_rate', 10)
    gas_rate = params.get('motorcycle_gas_rate', 0.65)
    gas_cap = params.get('motorcycle_gas_cap', 261)  # Gas cap for Motorcycle

    basic_salary = (final_target / 13.333) * basic_salary_rate
    bonus_orders = total_orders - final_target
    if bonus_orders > 0:
        bonus_amount = bonus_orders * bonus_rate
    else:
        bonus_amount = bonus_orders * penalty_rate

    gas_deserved = min(total_orders * gas_rate, gas_cap)
    gas_difference = gas_deserved - gas_usage
    total_salary = max(0, basic_salary + bonus_amount + gas_difference)

    return {
        "Basic_Salary": round(basic_salary, 2),
        "Bonus_Amount": round(bonus_amount, 2),
        "Gas_Deserved": round(gas_deserved, 2),
        "Gas_Difference": round(gas_difference, 2),
        "Total_Salary": round(total_salary, 2),
        "target": final_target
    }

def calculate_food_trial_salary(total_orders, target, gas_usage,
                                days_since_joining, total_revenue, params):
    target_v2 = days_since_joining * 13
    final_target = min(target, target_v2)
    basic_salary_rate = params.get('food_trial_basic_salary_rate',
                                   66.66666667)
    bonus_rate = params.get('food_trial_bonus_rate', 7)
    penalty_rate = params.get('food_trial_penalty_rate', 10)
    gas_rate = params.get('food_trial_gas_rate', 2.11)
    gas_cap = params.get('food_trial_gas_cap', 826)  # Gas cap for Food

    basic_salary = (final_target / 13) * basic_salary_rate

    bonus_orders = total_orders - final_target
    if bonus_orders > 0:
        bonus_amount = bonus_orders * bonus_rate
    else:
        bonus_amount = bonus_orders * penalty_rate

    gas_deserved = min(gas_rate * total_orders, gas_cap)
    gas_difference = gas_deserved - gas_usage

    total_salary = max(0, basic_salary + bonus_amount + gas_difference)

    return {
        "Basic_Salary": round(basic_salary, 2),
        "Bonus_Amount": round(bonus_amount, 2),
        "Gas_Deserved": round(gas_deserved, 2),
        "Gas_Difference": round(gas_difference, 2),
        "Total_Salary": round(total_salary, 2),
        "target": final_target
    }

def calculate_food_inhouse_new_salary(total_orders, target, gas_usage,
                                      days_since_joining, total_revenue,
                                      params):
    target_v2 = days_since_joining * 15.8333333
    final_target = min(target, target_v2)
    basic_salary_rate = params.get('food_inhouse_new_basic_salary_rate',
                                   66.66666667)
    bonus_rate = params.get('food_inhouse_new_bonus_rate', 7)
    penalty_rate = params.get('food_inhouse_new_penalty_rate', 10)
    gas_rate = params.get('food_inhouse_new_gas_rate', 1.739)
    gas_cap = params.get('food_inhouse_new_gas_cap', 826)  # Gas cap for Food

    basic_salary = (final_target / 15.83333333) * basic_salary_rate

    bonus_orders = total_orders - final_target
    if bonus_orders > 0:
        bonus_amount = bonus_orders * bonus_rate
    else:
        bonus_amount = bonus_orders * penalty_rate

    gas_deserved = min(gas_rate * total_orders, gas_cap)
    gas_difference = gas_deserved - gas_usage

    total_salary = max(0, basic_salary + bonus_amount + gas_difference)

    return {
        "Basic_Salary": round(basic_salary, 2),
        "Bonus_Amount": round(bonus_amount, 2),
        "Gas_Deserved": round(gas_deserved, 2),
        "Gas_Difference": round(gas_difference, 2),
        "Total_Salary": round(total_salary, 2),
        "target": final_target
    }

def calculate_food_inhouse_old_salary(total_orders, target, gas_usage,
                                      days_since_joining, total_revenue,
                                      params):
    target_v2 = days_since_joining * 15.8333333
    final_target = min(target, target_v2)
    basic_salary_rate = params.get('food_inhouse_old_basic_salary_rate',
                                   66.66666667)
    penalty_rate = params.get('food_inhouse_old_penalty_rate', 10)
    gas_rate = params.get('food_inhouse_old_gas_rate', 2.065)
    gas_cap = params.get('food_inhouse_old_gas_cap', 826)  # Gas cap for Food

    basic_salary = (final_target / 15.83333333) * basic_salary_rate

    bonus_orders = total_orders - final_target
    bonus_amount = 0
    if bonus_orders <= 0:
        bonus_amount = bonus_orders * penalty_rate
    else:
        tiers = [
            (124, 5),
            (100, 6),
            (100, 7),
            (100, 8),
            (float('inf'), 9)
        ]
        remaining_orders = bonus_orders
        for tier_limit, rate in tiers:
            orders_in_tier = min(remaining_orders, tier_limit)
            bonus_amount += orders_in_tier * rate
            remaining_orders -= orders_in_tier
            if remaining_orders <= 0:
                break

    gas_deserved = min(gas_rate * total_orders, gas_cap)
    gas_difference = gas_deserved - gas_usage

    total_salary = max(0, basic_salary + bonus_amount + gas_difference)

    return {
        "Basic_Salary": round(basic_salary, 2),
        "Bonus_Amount": round(bonus_amount, 2),
        "Gas_Deserved": round(gas_deserved, 2),
        "Gas_Difference": round(gas_difference, 2),
        "Total_Salary": round(total_salary, 2),
        "target": final_target
    }

def calculate_ecommerce_wh_salary(total_orders, target, gas_usage,
                                  days_since_joining, total_revenue, params):
    target2 = days_since_joining * 16.66667
    final_target = min(target, target2)
    basic_salary_rate = params.get('ecommerce_wh_basic_salary_rate',
                                   66.666667)
    bonus_rate = params.get('ecommerce_wh_bonus_rate', 8)
    penalty_rate = params.get('ecommerce_wh_penalty_rate', 10)
    gas_rate = params.get('ecommerce_wh_gas_rate', 15.03)
    gas_cap = params.get('ecommerce_wh_gas_cap', 452)  # Gas cap for Ecommerce

    basic_salary = (final_target / 16.6666667) * basic_salary_rate

    bonus_orders = total_orders - final_target
    if bonus_orders > 0:
        bonus_amount = bonus_orders * bonus_rate
    else:
        bonus_amount = bonus_orders * penalty_rate

    diesel_deserved = min((final_target / 16.666667) * gas_rate, gas_cap)
    gas_difference = diesel_deserved - gas_usage

    total_salary = max(0, basic_salary + bonus_amount + gas_difference)

    return {
        "Basic_Salary": round(basic_salary, 2),
        "Bonus_Amount": round(bonus_amount, 2),
        "Gas_Deserved": round(diesel_deserved, 2),
        "Gas_Difference": round(gas_difference, 2),
        "Total_Salary": round(total_salary, 2),
        "target": final_target
    }

def calculate_ecommerce_salary(total_orders, target, gas_usage,
                               days_since_joining, total_revenue, params):
    target2 = days_since_joining * 221
    final_target = min(target, target2)
    revenue_coefficient = params.get('ecommerce_revenue_coefficient',
                                     0.3016591252)
    basic_salary_rate = params.get('ecommerce_basic_salary_rate',
                                   66.66666667)
    gas_cap = params.get('ecommerce_gas_cap', 452)  # Gas cap for Ecommerce

    revenue_based_salary = total_revenue * revenue_coefficient
    target_based_salary = (final_target / 221) * basic_salary_rate
    basic_salary = min(revenue_based_salary, target_based_salary)

    bonus_revenue = max(0, total_revenue - final_target)
    if bonus_revenue <= 4000:
        bonus_amount = bonus_revenue * 0.55
    else:
        bonus_amount = (4000 * 0.55) + ((bonus_revenue - 4000) * 0.5)

    diesel_deserved = min(0.068 * total_revenue,
                          (final_target / 221) * 15.06, gas_cap)
    gas_difference = diesel_deserved - gas_usage

    total_salary = max(0, basic_salary + bonus_amount + gas_difference)

    return {
        "Basic_Salary": round(basic_salary, 2),
        "Bonus_Amount": round(bonus_amount, 2),
        "Gas_Deserved": round(diesel_deserved, 2),
        "Gas_Difference": round(gas_difference, 2),
        "Total_Salary": round(total_salary, 2),
        "target": final_target
    }

def calculate_ajeer_salary(total_orders, target, gas_usage,
                           days_since_joining, total_revenue, params):
    basic_salary_rate = params.get('ajeer_basic_salary_rate', 53.33333)
    penalty_rate = params.get('ajeer_penalty_rate', 10)
    gas_rate = params.get('ajeer_gas_rate', 2.065)
    gas_cap = params.get('ajeer_gas_cap', 826)  # Assuming same as Food

    basic_salary = (target / 13.333333333333334) * basic_salary_rate

    bonus_orders = total_orders - target
    bonus_amount = 0
    if bonus_orders <= 0:
        bonus_amount = bonus_orders * penalty_rate
    else:
        tiers = [
            (299, 6),
            (100, 7),
            (100, 8),
            (float('inf'), 9)
        ]
        remaining_orders = bonus_orders
        for tier_limit, rate in tiers:
            orders_in_tier = min(remaining_orders, tier_limit)
            bonus_amount += orders_in_tier * rate
            remaining_orders -= orders_in_tier
            if remaining_orders <= 0:
                break

    gas_deserved = min(gas_rate * total_orders, gas_cap)
    gas_difference = gas_deserved - gas_usage

    total_salary = max(0, basic_salary + bonus_amount + gas_difference)

    return {
        "Basic_Salary": round(basic_salary, 2),
        "Bonus_Amount": round(bonus_amount, 2),
        "Gas_Deserved": round(gas_deserved, 2),
        "Gas_Difference": round(gas_difference, 2),
        "Total_Salary": round(total_salary, 2),
        "target": target
    }



@app.route('/')
@login_required
def main():
    app.logger.debug("Main page accessed")
    try:
        return render_template('index.html')
    except Exception as e:
        app.logger.error(f"Error rendering index.html: {e}")
        return "Error rendering page", 500
    
@app.route('/salary')
@login_required
def salary():
    app.logger.debug("salary page accessed")
    try:
        return render_template('salary.html',calendar=calendar)
    except Exception as e:
        app.logger.error(f"Error rendering index.html: {e}")
        return "Error rendering page", 500

@app.route("/announcements")
@login_required
def announcements():
    app.logger.debug("Announcements page accessed")
    if "mobile_number" not in session:
        return redirect(url_for("login"))
    query = "SELECT * FROM `looker-barqdata-2030.master_saned.announcements`"
    announcements = execute_query(client, query)
    return render_template("announcements.html", announcements=announcements)

@app.route("/private_messages")
@login_required
def private_messages():
    app.logger.debug("Private messages page accessed")
    mobile_number = session.get('mobile_number')
    query = """
        SELECT message, timestamp
        FROM `looker-barqdata-2030.master_saned.private_messages`
        WHERE mobile_number = @mobile_number
    """
    params = [
        bigquery.ScalarQueryParameter('mobile_number', 'STRING', mobile_number)
    ]
    messages = execute_query(client, query, params=params)
    return render_template("private_messages.html", messages=messages)

@app.route('/vehicle_fleet', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def vehicles():
    client = get_bigquery_client()
    
    if request.method == 'GET':
        results = fetch_vehicle_logs(client)
        return render_template('vehicle_fleet.html', logs=results)

    elif request.method == 'POST':
        data = request.json
        try:
            insert_vehicle_log(client, data)
            return jsonify(success=True, message="Vehicle log added successfully")
        except KeyError as e:
            return jsonify(success=False, message=f"Missing key: {e}"), 400
    
    elif request.method == 'PUT':
        data = request.json
        try:
            update_vehicle_log(client, data)
            return jsonify(success=True, message="Vehicle log updated successfully")
        except KeyError as e:
            return jsonify(success=False, message=f"Missing key: {e}"), 400
    
    elif request.method == 'DELETE':
        date = request.args.get('date')
        delete_vehicle_log(client, date)
        return jsonify(success=True, message="Vehicle log deleted successfully")

@app.route('/vehicle_insights', methods=['GET'])
@login_required
def vehicle_insights():
    client = get_bigquery_client()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    try:
        results = fetch_vehicle_insights(client, start_date, end_date)
        return jsonify(results=[dict(row) for row in results])
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@app.route('/vehicle_charts', methods=['GET'])
@login_required
def vehicle_charts():
    client = get_bigquery_client()
    time_frame = request.args.get('time_frame', 'month')
    try:
        results = fetch_vehicle_charts(client, time_frame)
        return jsonify(results=[dict(row) for row in results])
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

# Register the Blueprint
app.register_blueprint(saned_bp, url_prefix='/saned')
app.register_blueprint(fetch_data_bp, url_prefix='/fetch_data')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
