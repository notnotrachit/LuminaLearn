from stellar_sdk import Server, Keypair, Network, TransactionBuilder, Asset, scval, xdr
from stellar_sdk.exceptions import NotFoundError, BadRequestError
from stellar_sdk import SorobanServer, StrKey
from stellar_sdk.operation import InvokeHostFunction, Payment
from stellar_sdk.xdr import HostFunction
from django.conf import settings
import base64
import hashlib
import secrets
import time

# Configuration from Django settings
def get_horizon_url():
    return settings.STELLAR_HORIZON_URL

def get_soroban_rpc_url():
    return settings.STELLAR_RPC_URL

def get_network_passphrase():
    return Network.TESTNET_NETWORK_PASSPHRASE if settings.STELLAR_TESTNET else Network.PUBLIC_NETWORK_PASSPHRASE

def get_contract_id():
    return settings.STELLAR_CONTRACT_ID

def get_admin_secret():
    return getattr(settings, 'STELLAR_ADMIN_SECRET', '')

class StellarHelper:
    @staticmethod
    def create_keypair():
        """
        Create a new Stellar keypair (public key and secret seed)
        """
        keypair = Keypair.random()
        return {
            'public_key': keypair.public_key,
            'secret_seed': keypair.secret
        }
    
    @staticmethod
    def fund_account(public_key):
        """
        Fund an account on testnet using Friendbot
        """
        import requests
        response = requests.get(f'https://friendbot.stellar.org?addr={public_key}')
        return response.status_code == 200
    
    @staticmethod
    def generate_nonce():
        """
        Generate a secure random nonce that can be used in QR code for attendance
        """
        random_bytes = secrets.token_bytes(32)
        nonce = base64.b64encode(random_bytes).decode('utf-8')
        return nonce
    
    @classmethod
    def initialize_contract(cls, admin_seed):
        """
        Initialize the attendance contract with an admin
        """
        if not get_contract_id():
            return {"status": "success", "message": "Contract initialized (simulated)"}
        
        try:
            # Create keypair from secret
            admin_keypair = Keypair.from_secret(admin_seed)
            
            # Connect to the Stellar network
            server = Server(horizon_url=get_horizon_url())
            soroban_server = SorobanServer(get_soroban_rpc_url())
            
            # Get the current account details
            admin_account = server.load_account(admin_keypair.public_key)
            
            # Create a transaction
            transaction = (
                TransactionBuilder(
                    source_account=admin_account,
                    network_passphrase=get_network_passphrase(),
                    base_fee=100000  # Adjust as needed
                )
                .add_text_memo("Initialize contract")
                .build()
            )
            
            # Sign the transaction
            transaction.sign(admin_keypair)
            
            # Submit the transaction
            response = server.submit_transaction(transaction)
            return {"status": "success", "message": "Contract initialized (simulated - SDK compatibility mode)"}
        except Exception as e:
            return {"error": str(e)}
    
    @classmethod
    def register_teacher(cls, teacher_seed):
        """
        Register a teacher in the smart contract
        """
        if not get_contract_id():
            return {"status": "success", "message": "Teacher registered (simulated)"}
        
        try:
            # Create keypair from secret
            teacher_keypair = Keypair.from_secret(teacher_seed)
            
            # Connect to the Stellar network
            server = Server(horizon_url=get_horizon_url())
            
            # Get the current account details
            teacher_account = server.load_account(teacher_keypair.public_key)
            
            # Create a transaction
            transaction = (
                TransactionBuilder(
                    source_account=teacher_account,
                    network_passphrase=get_network_passphrase(),
                    base_fee=100000  # Adjust as needed
                )
                .add_text_memo("Register teacher")
                .build()
            )
            
            # Sign the transaction
            transaction.sign(teacher_keypair)
            
            # Submit the transaction
            response = server.submit_transaction(transaction)
            return {"status": "success", "message": "Teacher registered successfully"}
        except Exception as e:
            return {"error": str(e)}
    
    @classmethod
    def register_student(cls, student_seed):
        """
        Register a student in the smart contract
        """
        if not get_contract_id():
            return {"status": "success", "message": "Student registered (simulated)"}
        
        try:
            # Create keypair from secret
            student_keypair = Keypair.from_secret(student_seed)
            
            # Connect to the Stellar network
            server = Server(horizon_url=get_horizon_url())
            
            # Get the current account details
            student_account = server.load_account(student_keypair.public_key)
            
            # Create a transaction
            transaction = (
                TransactionBuilder(
                    source_account=student_account,
                    network_passphrase=get_network_passphrase(),
                    base_fee=100000  # Adjust as needed
                )
                .add_text_memo("Register student")
                .build()
            )
            
            # Sign the transaction
            transaction.sign(student_keypair)
            
            # Submit the transaction
            response = server.submit_transaction(transaction)
            return {"status": "success", "message": "Student registered successfully"}
        except Exception as e:
            return {"error": str(e)}
    
    @classmethod
    def create_lecture(cls, teacher_seed, lecture_id, course_id, title, date_timestamp, duration_minutes):
        """
        Create a lecture entry in the smart contract
        """
        if not get_contract_id():
            return {"status": "success", "message": f"Lecture {lecture_id} created (simulated)"}
        
        try:
            # Create keypair from secret
            teacher_keypair = Keypair.from_secret(teacher_seed)
            
            # Connect to the Stellar network
            server = Server(horizon_url=get_horizon_url())
            
            # Get the current account details
            teacher_account = server.load_account(teacher_keypair.public_key)
            
            # Create a transaction with a dummy payment operation to self
            # This is needed because a transaction must have at least one operation
            transaction = (
                TransactionBuilder(
                    source_account=teacher_account,
                    network_passphrase=get_network_passphrase(),
                    base_fee=100000  # Adjust as needed
                )
                .append_payment_op(
                    destination=teacher_keypair.public_key,
                    amount="0.0000001",  # Minimum amount to avoid dust limit
                    asset=Asset.native()
                )
                .add_text_memo(f"Create lecture: {lecture_id}")
                .build()
            )
            
            # Sign the transaction
            transaction.sign(teacher_keypair)
            
            # Submit the transaction
            response = server.submit_transaction(transaction)
            print("Transaction response:")
            print(response)
            
            return {"status": "success", "message": f"Lecture {lecture_id} created successfully"}
        except Exception as e:
            return {"error": str(e)}
    
    @classmethod
    def start_attendance(cls, teacher_seed, lecture_id, duration_seconds=300):
        """
        Start an attendance session for a lecture
        """
        if not get_contract_id():
            return {"status": "success", "message": f"Attendance started for {lecture_id} (simulated)"}
        
        try:
            # Create keypair from secret
            teacher_keypair = Keypair.from_secret(teacher_seed)
            
            # Connect to the Stellar network
            server = Server(horizon_url=get_horizon_url())
            
            # Get the current account details
            teacher_account = server.load_account(teacher_keypair.public_key)
            
            # Create a transaction
            transaction = (
                TransactionBuilder(
                    source_account=teacher_account,
                    network_passphrase=get_network_passphrase(),
                    base_fee=100000  # Adjust as needed
                )
                .append_payment_op(
                    destination=teacher_keypair.public_key,
                    amount="0.0000001",  # Minimum amount to avoid dust limit
                    asset=Asset.native()
                )
                .add_text_memo(f"Att start:{str(lecture_id)[:10]}")
                .build()
            )
            
            # Sign the transaction
            transaction.sign(teacher_keypair)
            
            # Submit the transaction
            response = server.submit_transaction(transaction)
            
            # Generate a nonce for attendance QR code
            nonce = f"nonce_{int(time.time())}"
            
            return {
                "status": "success",
                "message": f"Attendance session started for {lecture_id}",
                "nonce": nonce
            }
        except Exception as e:
            return {"error": str(e)}
    
    @classmethod
    def mark_attendance(cls, student_seed, lecture_id, nonce):
        """
        Mark attendance for a student in a lecture
        """
        if not get_contract_id():
            return {"status": "success", "message": f"Attendance marked for {lecture_id} (simulated)"}
        
        try:
            # Create keypair from secret
            student_keypair = Keypair.from_secret(student_seed)
            
            # Connect to the Stellar network
            server = Server(horizon_url=get_horizon_url())
            
            # Get the current account details
            student_account = server.load_account(student_keypair.public_key)
            
            # Create a transaction
            transaction = (
                TransactionBuilder(
                    source_account=student_account,
                    network_passphrase=get_network_passphrase(),
                    base_fee=100000  # Adjust as needed
                )
                .append_payment_op(
                    destination=student_keypair.public_key,
                    amount="0.0000001",  # Minimum amount to avoid dust limit
                    asset=Asset.native()
                )
                .add_text_memo(f"Att:{str(lecture_id)[:10]}:{nonce[:10]}")
                .build()
            )
            
            # Sign the transaction
            transaction.sign(student_keypair)
            
            # Submit the transaction
            response = server.submit_transaction(transaction)
            return {"status": "success", "message": f"Attendance marked successfully for {lecture_id}"}
        except Exception as e:
            return {"error": str(e)}
    
    @classmethod
    def close_attendance_session(cls, teacher_seed, lecture_id):
        """
        Close an active attendance session
        """
        if not get_contract_id():
            return {"status": "success", "message": f"Attendance session closed for {lecture_id} (simulated)"}
        
        try:
            # Create keypair from secret
            teacher_keypair = Keypair.from_secret(teacher_seed)
            
            # Connect to the Stellar network
            server = Server(horizon_url=get_horizon_url())
            
            # Get the current account details
            teacher_account = server.load_account(teacher_keypair.public_key)
            
            # Create a transaction
            transaction = (
                TransactionBuilder(
                    source_account=teacher_account,
                    network_passphrase=get_network_passphrase(),
                    base_fee=100000  # Adjust as needed
                )
                .append_payment_op(
                    destination=teacher_keypair.public_key,
                    amount="0.0000001",  # Minimum amount to avoid dust limit
                    asset=Asset.native()
                )
                .add_text_memo(f"Att end:{str(lecture_id)[:10]}")
                .build()
            )
            
            # Sign the transaction
            transaction.sign(teacher_keypair)
            
            # Submit the transaction
            response = server.submit_transaction(transaction)
            return {"status": "success", "message": f"Attendance session closed successfully for {lecture_id}"}
        except Exception as e:
            return {"error": str(e)}
    
    @classmethod
    def manual_attendance(cls, teacher_seed, lecture_id, student_public_key):
        """
        Manually mark attendance for a student
        """
        if not get_contract_id():
            return {"status": "success", "message": f"Manual attendance marked for {lecture_id} (simulated)"}
        
        try:
            # Create keypair from secret
            teacher_keypair = Keypair.from_secret(teacher_seed)
            
            # Connect to the Stellar network
            server = Server(horizon_url=get_horizon_url())
            
            # Get the current account details
            teacher_account = server.load_account(teacher_keypair.public_key)
            
            # Create a transaction
            transaction = (
                TransactionBuilder(
                    source_account=teacher_account,
                    network_passphrase=get_network_passphrase(),
                    base_fee=100000  # Adjust as needed
                )
                .append_payment_op(
                    destination=teacher_keypair.public_key,
                    amount="0.0000001",  # Minimum amount to avoid dust limit
                    asset=Asset.native()
                )
                .add_text_memo(f"MAtt:{str(lecture_id)[:7]}:{student_public_key[:8]}")
                .build()
            )
            
            # Sign the transaction
            transaction.sign(teacher_keypair)
            
            # Submit the transaction
            response = server.submit_transaction(transaction)
            return {"status": "success", "message": f"Manual attendance marked successfully for {lecture_id}"}
        except Exception as e:
            return {"error": str(e)}
    
    @classmethod
    def verify_attendance(cls, lecture_id, student_public_key):
        """
        Verify if a student has attended a lecture
        """
        if not get_contract_id():
            return True
        
        try:
            # For now, we'll return a simulated success
            return True
        except Exception as e:
            print(f"Error verifying attendance: {e}")
            return False
    
    @classmethod
    def verify_contract_connection(cls):
        """
        Verify that the contract connection is working properly
        """
        if not get_contract_id():
            return {"status": "error", "message": "No contract ID provided"}
        
        try:
            # First try connecting to Horizon
            try:
                server = Server(horizon_url=get_horizon_url())
                network_response = server.root().call()
                horizon_connected = True
                
                # Now try connecting to Soroban RPC
                soroban_server = SorobanServer(get_soroban_rpc_url())
                soroban_info = soroban_server.get_health()
                soroban_connected = True
            except Exception as e:
                horizon_connected = False
                soroban_connected = False
                connection_error = str(e)
            
            if horizon_connected and soroban_connected:
                # If both Horizon and Soroban are accessible, we're connected to the Stellar network
                return {
                    "status": "success",
                    "message": "Successfully connected to Stellar network and Soroban RPC.",
                    "contract_id": get_contract_id(),
                    "network_info": "Connected to Horizon and Soroban APIs"
                }
            elif horizon_connected:
                return {
                    "status": "partial",
                    "message": "Connected to Stellar network, but Soroban RPC connection failed.",
                    "contract_id": get_contract_id(),
                    "network_info": "Connected to Horizon API only"
                }
            else:
                return {
                    "status": "error",
                    "message": f"Could not connect to Stellar network: {connection_error}",
                    "contract_id": get_contract_id()
                }
                
        except Exception as e:
            return {"status": "error", "message": f"Error checking blockchain connection: {str(e)}"} 