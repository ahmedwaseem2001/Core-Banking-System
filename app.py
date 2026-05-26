from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import traceback

# Import transaction logic functions
from transactions.transaction_logic import (
    initialize_database,
    add_new_customer,
    create_new_account,
    deposit_funds,
    withdraw_funds,
    transfer_funds,
    savepoint_tcl_demo,
    get_all_customers,
    get_all_accounts,
    get_all_transactions,
    get_all_audit_logs,
    get_account_balance,
    register_new_user,
    login_user
)

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)  # Enable CORS for all routes

# Initialize database on startup
initialize_database()


# ============================================================================
# STATIC FILE ROUTES
# ============================================================================

@app.route('/')
def serve_index():
    """Serve the main HTML page"""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/login')
def serve_login():
    """Serve the login page"""
    return send_from_directory(app.static_folder, 'login.html')


@app.route('/signup')
def serve_signup():
    """Serve the signup page"""
    return send_from_directory(app.static_folder, 'signup.html')


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.route('/api/auth/signup', methods=['POST'])
def handle_signup():
    """User registration"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "error": "No JSON data provided"}), 400

        user_id = register_new_user(
            username=data.get('username'),
            email=data.get('email'),
            password=data.get('password'),
            full_name=data.get('full_name')
        )
        return jsonify({
            "status": "success",
            "message": "User registered successfully!",
            "user_id": user_id
        }), 201
    except ValueError as e:
        return jsonify({"status": "error", "error": str(e)}), 400
    except Exception as e:
        print(f"Signup error: {str(e)}")
        traceback.print_exc()
        return jsonify({"status": "error", "error": "Internal server error"}), 500


@app.route('/api/auth/login', methods=['POST'])
def handle_login():
    """User login"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "error": "No JSON data provided"}), 400

        result = login_user(
            username=data.get('username'),
            password=data.get('password')
        )
        return jsonify({
            "status": "success",
            "message": "Login successful!",
            "data": result
        }), 200
    except ValueError as e:
        return jsonify({"status": "error", "error": str(e)}), 401
    except Exception as e:
        print(f"Login error: {str(e)}")
        traceback.print_exc()
        return jsonify({"status": "error", "error": "Internal server error"}), 500


# ============================================================================
# TEMPORARY COMPATIBILITY ROUTES
# ============================================================================

@app.route('/auth/signup', methods=['POST'])
def handle_signup_legacy():
    """Legacy signup route"""
    return handle_signup()


@app.route('/auth/login', methods=['POST'])
def handle_login_legacy():
    """Legacy login route"""
    return handle_login()


# ============================================================================
# CUSTOMER ENDPOINTS
# ============================================================================

@app.route('/api/customer', methods=['POST'])
def handle_add_customer():
    """Create a new customer"""
    try:
        data = request.get_json()
        customer_id = add_new_customer(
            name=data.get('name'),
            cnic=data.get('cnic'),
            contact=data.get('contact', '')
        )
        return jsonify({
            "status": "success",
            "message": "Customer created successfully!",
            "id": customer_id
        }), 201
    except ValueError as e:
        return jsonify({"status": "error", "error": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route('/api/customers', methods=['GET'])
def handle_get_customers():
    """Get all customers"""
    try:
        customers = get_all_customers()
        formatted_customers = [
            {
                "id": c["customer_id"],
                "name": c["name"],
                "cnic": c["cnic"],
                "contact": c.get("contact", "")
            }
            for c in customers
        ]
        return jsonify({
            "status": "success",
            "data": formatted_customers
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ============================================================================
# ACCOUNT ENDPOINTS
# ============================================================================

@app.route('/api/account', methods=['POST'])
def handle_create_account():
    """Create a new account"""
    try:
        data = request.get_json()
        account_no = create_new_account(
            customer_id=int(data.get('customer_id')),
            account_type=data.get('type', 'Savings'),
            initial_balance=float(data.get('initial_balance', 0))
        )
        return jsonify({
            "status": "success",
            "message": "Account created successfully!",
            "id": account_no
        }), 201
    except ValueError as e:
        return jsonify({"status": "error", "error": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route('/api/accounts', methods=['GET'])
def handle_get_accounts():
    """Get all accounts"""
    try:
        accounts = get_all_accounts()
        formatted_accounts = [
            {
                "acc_no": a["account_no"],
                "customer_id": a["customer_id"],
                "customer_name": a.get("customer_name", ""),
                "type": a["account_type"],
                "balance": a["balance"],
                "status": "Active"
            }
            for a in accounts
        ]
        return jsonify({
            "status": "success",
            "data": formatted_accounts
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route('/api/balance/<int:account_no>', methods=['GET'])
def handle_get_balance(account_no):
    """Get account balance"""
    try:
        balance = get_account_balance(account_no)
        return jsonify({
            "status": "success",
            "balance": balance
        }), 200
    except ValueError as e:
        return jsonify({"status": "error", "error": str(e)}), 404
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ============================================================================
# TRANSACTION ENDPOINTS
# ============================================================================

@app.route('/api/deposit', methods=['POST'])
def handle_deposit():
    """Deposit money into an account"""
    try:
        data = request.get_json()
        transaction_id = deposit_funds(
            account_no=int(data.get('account')),
            amount=float(data.get('amount'))
        )
        return jsonify({
            "status": "success",
            "message": "Deposit completed successfully!",
            "transaction_id": transaction_id
        }), 200
    except ValueError as e:
        return jsonify({"status": "error", "error": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route('/api/withdraw', methods=['POST'])
def handle_withdraw():
    """Withdraw money from an account"""
    try:
        data = request.get_json()
        transaction_id = withdraw_funds(
            account_no=int(data.get('account')),
            amount=float(data.get('amount'))
        )
        return jsonify({
            "status": "success",
            "message": "Withdrawal completed successfully!",
            "transaction_id": transaction_id
        }), 200
    except ValueError as e:
        return jsonify({"status": "error", "error": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route('/api/transfer', methods=['POST'])
def handle_transfer():
    """Transfer money between accounts"""
    try:
        data = request.get_json()
        transaction_id = transfer_funds(
            from_account_no=int(data.get('sender_id')),
            to_account_no=int(data.get('receiver_id')),
            amount=float(data.get('amount'))
        )
        return jsonify({
            "status": "success",
            "message": "Funds transferred successfully!",
            "transaction_id": transaction_id
        }), 200
    except ValueError as e:
        return jsonify({"status": "error", "error": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route('/api/transactions', methods=['GET'])
def handle_get_transactions():
    """Get all transactions"""
    try:
        transactions = get_all_transactions()
        formatted_transactions = [
            {
                "id": t["trans_id"],
                "type": t["transaction_type"],
                "from_acc": t.get("from_account"),
                "to_acc": t.get("to_account"),
                "amount": t["amount"],
                "datetime": t.get("date_time", "")
            }
            for t in transactions
        ]
        return jsonify({
            "status": "success",
            "data": formatted_transactions
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ============================================================================
# AUDIT ENDPOINTS
# ============================================================================

@app.route('/api/audit', methods=['GET'])
def handle_get_audit_logs():
    """Get all audit logs"""
    try:
        logs = get_all_audit_logs()
        formatted_logs = [
            {
                "id": log["log_id"],
                "operation": log["operation"],
                "table_affected": log.get("table_affected", ""),
                "user": log.get("user", "System"),
                "datetime": log.get("date_time", "")
            }
            for log in logs
        ]
        return jsonify({
            "status": "success",
            "data": formatted_logs
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ============================================================================
# SAVEPOINT DEMO ENDPOINT
# ============================================================================

@app.route('/api/savepoint-demo', methods=['POST'])
def handle_savepoint_demo():
    """Run the savepoint demonstration"""
    try:
        result = savepoint_tcl_demo()
        return jsonify({
            "status": "success",
            "message": result
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Check if API is running"""
    return jsonify({
        "status": "success",
        "message": "FAST Core Banking System API is running"
    }), 200


# ============================================================================
# CATCH ALL ROUTE
# ============================================================================

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🏦 FAST Core Banking System - SQLAlchemy Backend")
    print("=" * 60)
    print("Database: SQLite with SQLAlchemy ORM")
    print("Features: TCL Operations (COMMIT, ROLLBACK, SAVEPOINT)")
    print("Server starting on http://127.0.0.1:5000")
    print("Available Routes:")
    print("  - GET  /                 -> Main Application")
    print("  - GET  /login            -> Login Page")
    print("  - GET  /signup           -> Signup Page")
    print("  - POST /api/auth/signup  -> User Registration")
    print("  - POST /api/auth/login   -> User Login")
    print("  - POST /auth/signup      -> Legacy Signup")
    print("  - POST /auth/login       -> Legacy Login")
    print("  - GET  /api/health       -> Health Check")
    print("=" * 60 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5000)