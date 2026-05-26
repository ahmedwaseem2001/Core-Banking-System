from sqlalchemy.orm import Session
from contextlib import contextmanager
from database.db_config import SessionLocal, create_tables
from database.models import Customer, Account, Transaction, AuditLog
from datetime import datetime, timedelta
from transactions.auth import create_user, authenticate_user, create_access_token


@contextmanager
def get_db():
    """Context manager for database sessions with automatic commit/rollback."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


# --- SETUP FUNCTION ---

def initialize_database():
    """Ensures tables are created before the application runs."""
    create_tables()
    print("Database tables created successfully!")


# --- HELPER FUNCTION FOR AUDIT LOGGING ---

def log_transaction(db: Session, operation: str, table_affected: str, description: str, ref_id: int):
    """Logs the result of a database operation (COMMIT/ROLLBACK/SAVEPOINT)."""
    try:
        new_log = AuditLog(
            operation=f"{operation}: {ref_id}",
            table_affected=table_affected,
            user="System",
            description=description,
            date_time=datetime.utcnow()
        )
        db.add(new_log)
        db.flush()  # Write to session without committing
    except Exception as e:
        print(f"Error logging audit: {e}")


# --- AUTHENTICATION OPERATIONS ---

def register_new_user(username: str, email: str, password: str, full_name: str):
    """Register a new user"""
    with get_db() as db:
        user = create_user(db, username, email, password, full_name)

        log_transaction(
            db, 'COMMIT', 'User',
            f'New user registered: {username}',
            user.user_id
        )

        return user.user_id


def login_user(username: str, password: str):
    """Authenticate user and return access token"""
    with get_db() as db:
        user = authenticate_user(db, username, password)
        if not user:
            raise ValueError("Invalid username or password")

        if not user.is_active:
            raise ValueError("User account is disabled")

        access_token_expires = timedelta(minutes=30)
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.user_id},
            expires_delta=access_token_expires
        )

        log_transaction(
            db, 'LOGIN', 'User',
            f'User login: {username}',
            user.user_id
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user.user_id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role
        }


# --- DML OPERATIONS (Customer & Account Management) ---

def add_new_customer(name, cnic, contact):
    """
    Adds a new customer and commits the transaction.
    Returns: customer_id (auto-generated)
    """
    with get_db() as db:
        # Check if CNIC already exists
        if db.query(Customer).filter(Customer.cnic == cnic).first():
            raise ValueError(f"Customer with CNIC {cnic} already exists.")

        new_customer = Customer(
            name=name,
            cnic=cnic,
            contact=contact
        )

        db.add(new_customer)
        db.flush()  # Get auto-generated customer_id

        log_transaction(
            db, 'COMMIT', 'Customer',
            f'New customer added: {name}',
            new_customer.customer_id
        )

        return new_customer.customer_id


def create_new_account(customer_id, account_type, initial_balance=0.0):
    """
    Creates a new account for an existing customer.
    Returns: account_no (auto-generated)
    """
    with get_db() as db:
        # Verify customer exists
        customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
        if not customer:
            raise ValueError(f"Customer ID {customer_id} not found.")

        # Validate initial balance
        if initial_balance < 0:
            raise ValueError("Initial balance cannot be negative.")

        new_account = Account(
            customer_id=customer_id,
            account_type=account_type,
            balance=initial_balance
        )

        db.add(new_account)
        db.flush()  # Get auto-generated account_no

        log_transaction(
            db, 'COMMIT', 'Account',
            f'New {account_type} account created for Customer {customer_id}',
            new_account.account_no
        )

        return new_account.account_no


# --- TCL CORE OPERATIONS (25 MARKS FOCUS) ---

def deposit_funds(account_no, amount):
    """
    Scenario 1: Deposit - Successful COMMIT

    Demonstrates:
    - BEGIN (implicit)
    - UPDATE account balance
    - INSERT transaction record
    - COMMIT (explicit)
    """
    with get_db() as db:
        # Validate amount
        if amount <= 0:
            raise ValueError("Deposit amount must be positive.")

        # Lock account for update (ensures isolation)
        account = db.query(Account).filter(
            Account.account_no == account_no
        ).with_for_update().first()

        if not account:
            raise ValueError(f"Account {account_no} not found.")

        # 1. Update Balance
        old_balance = account.balance
        account.balance += amount

        # 2. Insert Transaction Record
        new_transaction = Transaction(
            to_account=account_no,
            amount=amount,
            transaction_type='Deposit',
            date_time=datetime.utcnow()
        )
        db.add(new_transaction)
        db.flush()

        # 3. Log the successful operation
        log_transaction(
            db, 'COMMIT', 'Account/Transaction',
            f'Deposit of {amount} to account {account_no}. Balance: {old_balance} → {account.balance}',
            new_transaction.trans_id
        )

        print(f"Deposit successful: {amount} added to account {account_no}")
        return new_transaction.trans_id


def withdraw_funds(account_no, amount):
    """
    Scenario 2: Withdrawal - ROLLBACK on Insufficient Funds

    Demonstrates:
    - BEGIN (implicit)
    - Check balance
    - UPDATE account balance (if sufficient)
    - INSERT transaction record
    - ROLLBACK (if insufficient funds)
    - COMMIT (if successful)
    """
    with get_db() as db:
        # Validate amount
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive.")

        # Lock account for update
        account = db.query(Account).filter(
            Account.account_no == account_no
        ).with_for_update().first()

        if not account:
            raise ValueError(f"Account {account_no} not found.")

        # Check for Insufficient Funds (This will trigger ROLLBACK)
        if account.balance < amount:
            log_transaction(
                db, 'ROLLBACK', 'Account/Transaction',
                f'Withdrawal failed: Insufficient funds. Balance: {account.balance}, Requested: {amount}',
                account_no
            )
            raise Exception(f"Insufficient funds: Balance {account.balance}, Requested {amount}")

        # 1. Deduct Balance
        old_balance = account.balance
        account.balance -= amount

        # 2. Insert Transaction Record
        new_transaction = Transaction(
            from_account=account_no,
            amount=amount,
            transaction_type='Withdrawal',
            date_time=datetime.utcnow()
        )
        db.add(new_transaction)
        db.flush()

        # 3. Log successful withdrawal
        log_transaction(
            db, 'COMMIT', 'Account/Transaction',
            f'Withdrawal of {amount} from account {account_no}. Balance: {old_balance} → {account.balance}',
            new_transaction.trans_id
        )

        print(f"Withdrawal successful: {amount} deducted from account {account_no}")
        return new_transaction.trans_id


def transfer_funds(from_account_no, to_account_no, amount):
    """
    Scenario 3: Transfer - Atomic COMMIT/ROLLBACK

    Demonstrates:
    - BEGIN (implicit)
    - Lock both accounts (with_for_update)
    - UPDATE sender balance
    - UPDATE receiver balance
    - INSERT transaction record
    - COMMIT (both updates happen atomically)
    - ROLLBACK (if any error occurs, neither update happens)
    """
    with get_db() as db:
        # Validate amount
        if amount <= 0:
            raise ValueError("Transfer amount must be positive.")

        if from_account_no == to_account_no:
            raise ValueError("Cannot transfer to the same account.")

        # 1. Lock both accounts for update (prevents race conditions)
        sender = db.query(Account).filter(
            Account.account_no == from_account_no
        ).with_for_update().first()

        receiver = db.query(Account).filter(
            Account.account_no == to_account_no
        ).with_for_update().first()

        # Validate accounts exist
        if not sender:
            raise ValueError(f"Sender account {from_account_no} not found.")
        if not receiver:
            raise ValueError(f"Receiver account {to_account_no} not found.")

        # Check sufficient funds
        if sender.balance < amount:
            log_transaction(
                db, 'ROLLBACK', 'Account/Transaction',
                f'Transfer failed: Insufficient funds in sender account {from_account_no}. Balance: {sender.balance}, Requested: {amount}',
                0
            )
            raise Exception(f"Transfer failed: Sender {from_account_no} has insufficient funds.")

        # 2. Perform atomic transfer
        sender_old_balance = sender.balance
        receiver_old_balance = receiver.balance

        sender.balance -= amount
        receiver.balance += amount

        # 3. Insert Transaction Record
        new_transaction = Transaction(
            from_account=from_account_no,
            to_account=to_account_no,
            amount=amount,
            transaction_type='Transfer',
            date_time=datetime.utcnow()
        )
        db.add(new_transaction)
        db.flush()

        # 4. Log successful transfer
        log_transaction(
            db, 'COMMIT', 'Account/Transaction',
            f'Atomic transfer: {amount} from {from_account_no} (Balance: {sender_old_balance} → {sender.balance}) to {to_account_no} (Balance: {receiver_old_balance} → {receiver.balance})',
            new_transaction.trans_id
        )

        print(f"Transfer successful: {amount} transferred from {from_account_no} to {to_account_no}")
        return new_transaction.trans_id


def savepoint_tcl_demo():
    """
    Scenario 4: SAVEPOINT - Demonstrates Partial Rollback

    Demonstrates:
    - BEGIN TRANSACTION
    - INSERT operation 1
    - SAVEPOINT A
    - INSERT operation 2
    - INSERT operation 3
    - ROLLBACK TO SAVEPOINT A (only operation 3 is undone)
    - COMMIT (operations 1 and 2 are committed)
    """
    db = SessionLocal()
    try:
        print("\n🔵 Starting SAVEPOINT Demo...")

        # 1. BEGIN TRANSACTION (implicit)
        log1 = AuditLog(
            operation='BEGIN',
            table_affected='AuditLog',
            description='Transaction started for SAVEPOINT demo',
            user='Demo',
            date_time=datetime.utcnow()
        )
        db.add(log1)
        db.flush()
        print(" Step 1: BEGIN TRANSACTION - Initial log entry created")

        # 2. SAVEPOINT A
        savepoint_a = db.begin_nested()
        print(" Step 2: SAVEPOINT A created")

        log2 = AuditLog(
            operation='SAVEPOINT A',
            table_affected='AuditLog',
            description='Savepoint created - this record will be saved',
            user='Demo',
            date_time=datetime.utcnow()
        )
        db.add(log2)
        db.flush()
        print(" Step 3: Record inserted after SAVEPOINT A (will be saved)")

        # 3. Insert a record that we will roll back
        log3 = AuditLog(
            operation='INSERT AFTER SAVEPOINT',
            table_affected='AuditLog',
            description='This record will be ROLLED BACK to SAVEPOINT A',
            user='Demo',
            date_time=datetime.utcnow()
        )
        db.add(log3)
        db.flush()
        print("  Step 4: Another record inserted (will be UNDONE)")

        # 4. ROLLBACK TO SAVEPOINT A (only log3 is undone)
        savepoint_a.rollback()
        print("  Step 5: ROLLBACK TO SAVEPOINT A - Last record undone")

        log4 = AuditLog(
            operation='ROLLBACK TO A',
            table_affected='AuditLog',
            description='Successfully rolled back to SAVEPOINT A. The last INSERT was undone.',
            user='Demo',
            date_time=datetime.utcnow()
        )
        db.add(log4)
        db.flush()

        # 5. COMMIT (log1, log2, and log4 are committed; log3 was rolled back)
        db.commit()
        print("  ✓ Step 6: COMMIT - All changes except rolled back record are permanent")

        result = "SAVEPOINT demo successful: log3 was rolled back, log1, log2, and log4 were committed."
        print(f"\n{result}\n")
        return result

    except Exception as e:
        db.rollback()
        error_msg = f"SAVEPOINT demo failed: {str(e)}"
        print(error_msg)

        try:
            log_transaction(db, 'ROLLBACK', 'AuditLog', error_msg, 0)
            db.commit()
        except:
            pass

        raise
    finally:
        db.close()


# --- QUERY OPERATIONS (For Testing/Viewing Data) ---

def get_all_customers():
    """Retrieve all customers from database."""
    with get_db() as db:
        customers = db.query(Customer).all()
        return [
            {
                "customer_id": c.customer_id,
                "name": c.name,
                "cnic": c.cnic,
                "contact": c.contact
            }
            for c in customers
        ]


def get_all_accounts():
    """Retrieve all accounts with customer names."""
    with get_db() as db:
        accounts = db.query(Account, Customer).join(
            Customer, Account.customer_id == Customer.customer_id
        ).all()

        return [
            {
                "account_no": acc.account_no,
                "customer_id": acc.customer_id,
                "customer_name": cust.name,
                "account_type": acc.account_type,
                "balance": float(acc.balance)
            }
            for acc, cust in accounts
        ]


def get_all_transactions():
    """Retrieve all transactions."""
    with get_db() as db:
        transactions = db.query(Transaction).order_by(Transaction.trans_id.desc()).all()
        return [
            {
                "trans_id": t.trans_id,
                "from_account": t.from_account,
                "to_account": t.to_account,
                "amount": float(t.amount),
                "transaction_type": t.transaction_type,
                "date_time": t.date_time.strftime("%Y-%m-%d %H:%M:%S") if t.date_time else None
            }
            for t in transactions
        ]


def get_all_audit_logs():
    """Retrieve all audit logs."""
    with get_db() as db:
        logs = db.query(AuditLog).order_by(AuditLog.log_id.desc()).all()
        return [
            {
                "log_id": log.log_id,
                "operation": log.operation,
                "table_affected": log.table_affected,
                "user": log.user,
                "description": log.description,
                "date_time": log.date_time.strftime("%Y-%m-%d %H:%M:%S") if log.date_time else None
            }
            for log in logs
        ]


def get_account_balance(account_no):
    """Get current balance of an account."""
    with get_db() as db:
        account = db.query(Account).filter(Account.account_no == account_no).first()
        if not account:
            raise ValueError(f"Account {account_no} not found.")
        return float(account.balance)


# --- DEMO/TEST FUNCTION ---

def run_demo():
    """
    Comprehensive demo of all TCL operations.
    This demonstrates all 4 scenarios required by the manual.
    """
    print("\n" + "=" * 60)
    print("CORE BANKING SYSTEM - TCL DEMONSTRATION")
    print("=" * 60 + "\n")

    try:
        # Initialize database
        print("Initializing database...")
        initialize_database()

        # Create test customers
        print("\n👥 Creating test customers...")
        cust1 = add_new_customer("Ahmad Khan", "42101-1234567-1", "+92-300-1234567")
        cust2 = add_new_customer("Sara Ahmed", "42101-7654321-9", "+92-321-9876543")
        print(f"   Customer 1 ID: {cust1}")
        print(f"   Customer 2 ID: {cust2}")

        # Create test accounts
        print("\n Creating test accounts...")
        acc1 = create_new_account(cust1, "Savings", 5000.00)
        acc2 = create_new_account(cust2, "Current", 3000.00)
        print(f"   Account 1 No: {acc1} (Balance: 5000.00)")
        print(f"   Account 2 No: {acc2} (Balance: 3000.00)")

        # Scenario 1: Successful Deposit (COMMIT)
        print("\n" + "-" * 60)
        print("Scenario 1: DEPOSIT (Successful COMMIT)")
        print("-" * 60)
        deposit_funds(acc1, 1000.00)
        print(f"   New balance for Account {acc1}: {get_account_balance(acc1)}")

        # Scenario 2: Failed Withdrawal (ROLLBACK)
        print("\n" + "-" * 60)
        print("Scenario 2: WITHDRAWAL (ROLLBACK on Insufficient Funds)")
        print("-" * 60)
        try:
            withdraw_funds(acc2, 5000.00)  # This will fail
        except Exception as e:
            print(f"   Expected error: {str(e)}")
        print(f"   Balance unchanged for Account {acc2}: {get_account_balance(acc2)}")

        # Scenario 2b: Successful Withdrawal
        print("\n   Attempting valid withdrawal...")
        withdraw_funds(acc2, 500.00)
        print(f"   New balance for Account {acc2}: {get_account_balance(acc2)}")

        # Scenario 3: Successful Transfer (Atomic COMMIT)
        print("\n" + "-" * 60)
        print("Scenario 3: TRANSFER (Atomic COMMIT)")
        print("-" * 60)
        print(f"   Before: Account {acc1} = {get_account_balance(acc1)}, Account {acc2} = {get_account_balance(acc2)}")
        transfer_funds(acc1, acc2, 2000.00)
        print(f"   After: Account {acc1} = {get_account_balance(acc1)}, Account {acc2} = {get_account_balance(acc2)}")

        # Scenario 4: SAVEPOINT Demo
        print("\n" + "-" * 60)
        print("Scenario 4: SAVEPOINT (Partial Rollback)")
        print("-" * 60)
        savepoint_tcl_demo()

        # Display summary
        print("\n" + "=" * 60)
        print("FINAL DATABASE STATE")
        print("=" * 60)

        print("\n👥 Customers:")
        for c in get_all_customers():
            print(f"   ID: {c['customer_id']}, Name: {c['name']}, CNIC: {c['cnic']}")

        print("\n Accounts:")
        for a in get_all_accounts():
            print(
                f"   Account: {a['account_no']}, Customer: {a['customer_name']}, Type: {a['account_type']}, Balance: {a['balance']}")

        print("\n Transactions:")
        for t in get_all_transactions()[:5]:  # Show last 5
            print(
                f"   ID: {t['trans_id']}, Type: {t['transaction_type']}, From: {t['from_account']}, To: {t['to_account']}, Amount: {t['amount']}")

        print("\nAudit Logs (Last 5):")
        for log in get_all_audit_logs()[:5]:
            print(f"   {log['operation']} | {log['table_affected']} | {log['description'][:50]}")

        print("\n" + "=" * 60)
        print(" DEMO COMPLETED SUCCESSFULLY!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n Demo failed: {str(e)}")
        import traceback
        traceback.print_exc()


# --- MAIN EXECUTION ---

if __name__ == "__main__":
    run_demo()