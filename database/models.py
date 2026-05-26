from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database.db_config import Base

class Customer(Base):
    __tablename__ = 'customer'

    # Primary Key
    customer_id = Column(Integer, primary_key=True, index=True)

    # Required Fields based on Project Manual
    name = Column(String(100), nullable=False)
    cnic = Column(String(15), nullable=False, unique=True)
    contact = Column(String(15))

    # Relationship
    accounts = relationship("Account", back_populates="customer")


class Account(Base):
    __tablename__ = 'account'

    # Primary Key
    account_no = Column(Integer, primary_key=True, index=True)

    # Foreign Key
    customer_id = Column(Integer, ForeignKey('customer.customer_id'), nullable=False)

    # CHANGE 'type' to 'account_type' to match your backend
    account_type = Column(String(50), nullable=False)
    balance = Column(Float, nullable=False, default=0.0)

    # Relationship
    customer = relationship("Customer", back_populates="accounts")


class Transaction(Base):
    __tablename__ = 'transaction'

    # Primary Key
    trans_id = Column(Integer, primary_key=True, index=True)

    # Foreign Keys (Links to Account)
    from_account = Column(Integer, ForeignKey('account.account_no'), nullable=True) # Nullable for Deposit
    to_account = Column(Integer, ForeignKey('account.account_no'), nullable=True)   # Nullable for Withdrawal

    amount = Column(Float, nullable=False)
    transaction_type = Column(String(50), nullable=False) # CHANGED from 'type' to 'transaction_type'
    date_time = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = 'audit_log'

    # Primary Key
    log_id = Column(Integer, primary_key=True, index=True)

    # Log details
    operation = Column(String(100), nullable=False)
    table_affected = Column(String(100))
    user = Column(String(100))
    description = Column(Text)
    date_time = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = 'user'

    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), default='user')  # 'user' or 'admin'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)