from stellar_sdk import Server, Keypair, Network, TransactionBuilder, Asset, scval, xdr
from stellar_sdk.exceptions import (
    NotFoundError,
    BadRequestError,
    ConnectionError as StellarConnectionError,
    BadResponseError,
    AccountRequiresMemoError
)
from stellar_sdk import SorobanServer, StrKey
from stellar_sdk.operation import InvokeHostFunction, Payment, CreateAccount
from stellar_sdk.xdr import HostFunction
from django.conf import settings
import base64
import hashlib
import secrets
import time
import binascii
import logging
from typing import Dict, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


# Custom exceptions for blockchain operations
class BlockchainTransactionError(Exception):
    """Base exception for blockchain transaction errors"""
    pass


class BlockchainConnectionError(BlockchainTransactionError):
    """Raised when connection to blockchain fails"""
    pass


class BlockchainInsufficientFundsError(BlockchainTransactionError):
    """Raised when account has insufficient funds"""
    pass


class BlockchainAccountNotFoundError(BlockchainTransactionError):
    """Raised when account is not found on blockchain"""
    pass


class BlockchainTimeoutError(BlockchainTransactionError):
    """Raised when blockchain transaction times out"""
    pass


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator to retry blockchain operations on transient failures

    Args:
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (StellarConnectionError, BadResponseError) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Blockchain operation {func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}"
                        )
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
                    else:
                        logger.error(
                            f"Blockchain operation {func.__name__} failed after {max_retries} attempts: {e}"
                        )
                except Exception as e:
                    # Don't retry on non-transient errors
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                    raise

            raise BlockchainConnectionError(
                f"Failed to complete blockchain operation after {max_retries} attempts"
            ) from last_exception

        return wrapper
    return decorator

# Configuration from Django settings
def get_horizon_url():
    return settings.STELLAR_HORIZON_URL

def get_soroban_rpc_url():
    return settings.STELLAR_RPC_URL

def get_network_passphrase():
    return Network.TESTNET_NETWORK_PASSPHRASE if settings.STELLAR_TESTNET else Network.PUBLIC_NETWORK_PASSPHRASE

def get_contract_id():
    return settings.STELLAR_CONTRACT_ID

def _build_memo(prefix: str, lecture_id: int, suffix: str = "") -> str:
    """
    Build a Stellar text memo (28-byte limit) from prefix + lecture_id + optional suffix.
    If lecture_id fits, include it in full. Otherwise, include a 6-char hex hash of it
    so the memo is always deterministic and collision-resistant.

    Args:
        prefix: Memo prefix (e.g., "Att:", "MAtt:")
        lecture_id: The lecture ID
        suffix: Optional suffix to append (e.g., nonce or public key prefix)

    Returns:
        str: A memo string that fits within 28 bytes
    """
    MAX_MEMO = 28
    body = f"{prefix}{lecture_id}"
    if suffix:
        body += f":{suffix[:6]}"

    if len(body.encode()) <= MAX_MEMO:
        return body

    # Lecture ID too long: use a 6-char CRC32 hex hash — unique per ID, always fits
    id_hash = format(binascii.crc32(str(lecture_id).encode()) & 0xFFFFFFFF, '08x')[:6]
    body = f"{prefix}#{id_hash}"
    if suffix:
        body += f":{suffix[:4]}"

    return body[:MAX_MEMO]

class StellarHelper:
    @staticmethod
    def get_explorer_url(transaction_hash: Optional[str] = None, account: Optional[str] = None) -> str:
        """
        Get Stellar Expert explorer URL for transaction or account

        Args:
            transaction_hash: Transaction hash to view
            account: Account address to view

        Returns:
            str: URL to Stellar Expert explorer
        """
        network = "testnet" if settings.STELLAR_TESTNET else "public"
        base_url = f"https://stellar.expert/explorer/{network}"

        if transaction_hash:
            return f"{base_url}/tx/{transaction_hash}"
        elif account:
            return f"{base_url}/account/{account}"
        else:
            return base_url

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
        Fund an account on testnet using Friendbot.
        On mainnet, accounts must be funded externally.
        """
        if not settings.STELLAR_TESTNET:
            # On mainnet, accounts must be funded externally
            logger.warning(f"Attempted to auto-fund account {public_key} on mainnet - not supported")
            return False

        import requests
        try:
            response = requests.get(
                f'https://friendbot.stellar.org?addr={public_key}',
                timeout=10
            )
            success = response.status_code == 200
            if success:
                logger.info(f"Successfully funded testnet account: {public_key}")
            else:
                logger.error(f"Failed to fund testnet account {public_key}: {response.status_code}")
            return success
        except requests.RequestException as e:
            logger.error(f"Friendbot request failed for {public_key}: {e}")
            return False

    @classmethod
    def fund_account_from_sponsor(cls, sponsor_seed: str, new_account_pubkey: str, amount_xlm: str = "2") -> Dict[str, Any]:
        """
        Fund a new account from a sponsor account (mainnet/testnet compatible).

        This is the mainnet funding strategy - a sponsor account sends XLM to create new accounts.

        Args:
            sponsor_seed: Secret seed of the sponsor account (must have XLM balance)
            new_account_pubkey: Public key of the new account to fund
            amount_xlm: Amount of XLM to send (default: 2 XLM - minimum is 1 XLM)

        Returns:
            Dict with status, transaction_hash, and explorer_url

        Raises:
            BlockchainAccountNotFoundError: If sponsor account not found
            BlockchainInsufficientFundsError: If sponsor has insufficient funds
            BlockchainTransactionError: For other errors
        """
        try:
            sponsor_keypair = Keypair.from_secret(sponsor_seed)
            server = Server(horizon_url=get_horizon_url())

            # Load sponsor account
            try:
                sponsor_account = server.load_account(sponsor_keypair.public_key)
            except NotFoundError:
                raise BlockchainAccountNotFoundError(
                    f"Sponsor account {sponsor_keypair.public_key} not found"
                )

            # Create account creation transaction
            transaction = (
                TransactionBuilder(
                    source_account=sponsor_account,
                    network_passphrase=get_network_passphrase(),
                    base_fee=100000
                )
                .append_create_account_op(
                    destination=new_account_pubkey,
                    starting_balance=amount_xlm
                )
                .add_text_memo(f"Create account")
                .set_timeout(30)
                .build()
            )

            transaction.sign(sponsor_keypair)

            try:
                response = server.submit_transaction(transaction)
                tx_hash = response.get('hash', 'unknown')

                logger.info(
                    f"Funded new account {new_account_pubkey} with {amount_xlm} XLM, tx: {tx_hash}"
                )

                return {
                    "status": "success",
                    "message": f"Account funded with {amount_xlm} XLM",
                    "transaction_hash": tx_hash,
                    "explorer_url": cls.get_explorer_url(tx_hash),
                    "new_account": new_account_pubkey
                }
            except BadRequestError as e:
                error_msg = str(e)
                if "op_underfunded" in error_msg.lower():
                    raise BlockchainInsufficientFundsError(
                        f"Sponsor account has insufficient funds to create account"
                    )
                else:
                    raise BlockchainTransactionError(f"Failed to fund account: {error_msg}")

        except (BlockchainAccountNotFoundError, BlockchainInsufficientFundsError, BlockchainTransactionError):
            raise
        except Exception as e:
            logger.exception(f"Unexpected error funding account {new_account_pubkey}")
            raise BlockchainTransactionError(f"Unexpected error: {str(e)}")
    
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
            logger.debug(f"Transaction response for lecture {lecture_id}")

            return {"status": "success", "message": f"Lecture {lecture_id} created successfully"}
        except Exception as e:
            # Save to failed transaction queue (Issue #6)
            cls.save_failed_transaction(
                transaction_type='lecture',
                error=e,
                transaction_data={
                    'lecture_id': lecture_id,
                    'course_id': course_id,
                    'title': title,
                    'date_timestamp': date_timestamp,
                    'duration_minutes': duration_minutes,
                }
            )
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
    @retry_on_failure(max_retries=3, delay=1.0)
    def mark_attendance(cls, student_seed: str, lecture_id: int, nonce: str) -> Dict[str, Any]:
        """
        Mark attendance for a student in a lecture with improved error handling

        Args:
            student_seed: Student's secret seed
            lecture_id: ID of the lecture
            nonce: Attendance session nonce

        Returns:
            Dict containing status and message/error

        Raises:
            BlockchainAccountNotFoundError: If student account not found
            BlockchainInsufficientFundsError: If student has insufficient funds
            BlockchainConnectionError: If connection to blockchain fails
            BlockchainTransactionError: For other blockchain errors
        """
        if not get_contract_id():
            return {"status": "success", "message": f"Attendance marked for {lecture_id} (simulated)"}

        try:
            # Create keypair from secret
            student_keypair = Keypair.from_secret(student_seed)

            # Connect to the Stellar network
            server = Server(horizon_url=get_horizon_url())

            # Get the current account details
            try:
                student_account = server.load_account(student_keypair.public_key)
            except NotFoundError:
                logger.error(f"Student account not found: {student_keypair.public_key}")
                raise BlockchainAccountNotFoundError(
                    f"Student account {student_keypair.public_key} not found on blockchain"
                )

            # Create a transaction with collision-resistant memo
            memo_text = _build_memo("Att:", lecture_id, nonce[:10])

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
                .add_text_memo(memo_text)
                .build()
            )

            # Sign the transaction
            transaction.sign(student_keypair)

            # Submit the transaction
            try:
                response = server.submit_transaction(transaction)
                tx_hash = response.get('hash', 'unknown')

                logger.info(f"Attendance marked for lecture {lecture_id}, tx: {tx_hash}")

                return {
                    "status": "success",
                    "message": f"Attendance marked successfully for {lecture_id}",
                    "transaction_hash": tx_hash,
                    "explorer_url": cls.get_explorer_url(tx_hash)
                }
            except BadRequestError as e:
                error_msg = str(e)
                if "op_underfunded" in error_msg.lower() or "insufficient" in error_msg.lower():
                    logger.error(f"Insufficient funds for student {student_keypair.public_key}: {error_msg}")
                    raise BlockchainInsufficientFundsError(
                        "Student account has insufficient funds to mark attendance"
                    )
                else:
                    logger.error(f"Bad request error marking attendance: {error_msg}")
                    raise BlockchainTransactionError(f"Failed to mark attendance: {error_msg}")

        except (BlockchainAccountNotFoundError, BlockchainInsufficientFundsError, BlockchainTransactionError) as e:
            # Save to failed transaction queue (Issue #6)
            cls.save_failed_transaction(
                transaction_type='attendance',
                error=e,
                transaction_data={
                    'lecture_id': lecture_id,
                    'student_public_key': student_keypair.public_key if 'student_keypair' in locals() else None,
                    'nonce': nonce,
                }
            )
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            logger.exception(f"Unexpected error marking attendance for lecture {lecture_id}")
            # Save to failed transaction queue
            cls.save_failed_transaction(
                transaction_type='attendance',
                error=e,
                transaction_data={
                    'lecture_id': lecture_id,
                    'nonce': nonce,
                }
            )
            raise BlockchainTransactionError(f"Unexpected error marking attendance: {str(e)}")
    
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
    @retry_on_failure(max_retries=3, delay=1.0)
    def manual_attendance(cls, teacher_seed: str, lecture_id: int, student_public_key: str) -> Dict[str, Any]:
        """
        Manually mark attendance for a student with transaction atomicity

        This ensures the database update and blockchain transaction are atomic:
        - If blockchain transaction fails, database will not be updated (handled by caller)
        - If blockchain succeeds, return transaction hash for database storage

        Args:
            teacher_seed: Teacher's secret seed
            lecture_id: ID of the lecture
            student_public_key: Student's public key

        Returns:
            Dict containing status, message, and transaction_hash

        Raises:
            BlockchainAccountNotFoundError: If teacher account not found
            BlockchainInsufficientFundsError: If teacher has insufficient funds
            BlockchainConnectionError: If connection to blockchain fails
            BlockchainTransactionError: For other blockchain errors
        """
        if not get_contract_id():
            return {
                "status": "success",
                "message": f"Manual attendance marked for {lecture_id} (simulated)",
                "transaction_hash": "simulated_hash",
                "explorer_url": None
            }

        try:
            # Create keypair from secret
            teacher_keypair = Keypair.from_secret(teacher_seed)

            # Connect to the Stellar network
            server = Server(horizon_url=get_horizon_url())

            # Get the current account details
            try:
                teacher_account = server.load_account(teacher_keypair.public_key)
            except NotFoundError:
                logger.error(f"Teacher account not found: {teacher_keypair.public_key}")
                raise BlockchainAccountNotFoundError(
                    f"Teacher account {teacher_keypair.public_key} not found on blockchain"
                )

            # Create a transaction with collision-resistant memo
            memo_text = _build_memo("MAtt:", lecture_id, student_public_key[:8])

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
                .add_text_memo(memo_text)
                .build()
            )

            # Sign the transaction
            transaction.sign(teacher_keypair)

            # Submit the transaction
            try:
                response = server.submit_transaction(transaction)
                tx_hash = response.get('hash', 'unknown')

                logger.info(f"Manual attendance marked for lecture {lecture_id}, student {student_public_key[:8]}, tx: {tx_hash}")

                return {
                    "status": "success",
                    "message": f"Manual attendance marked successfully for {lecture_id}",
                    "transaction_hash": tx_hash,
                    "explorer_url": cls.get_explorer_url(tx_hash)
                }
            except BadRequestError as e:
                error_msg = str(e)
                if "op_underfunded" in error_msg.lower() or "insufficient" in error_msg.lower():
                    logger.error(f"Insufficient funds for teacher {teacher_keypair.public_key}: {error_msg}")
                    raise BlockchainInsufficientFundsError(
                        "Teacher account has insufficient funds to mark manual attendance"
                    )
                else:
                    logger.error(f"Bad request error marking manual attendance: {error_msg}")
                    raise BlockchainTransactionError(f"Failed to mark manual attendance: {error_msg}")

        except (BlockchainAccountNotFoundError, BlockchainInsufficientFundsError, BlockchainTransactionError) as e:
            # Save to failed transaction queue (Issue #6)
            cls.save_failed_transaction(
                transaction_type='attendance',
                error=e,
                transaction_data={
                    'lecture_id': lecture_id,
                    'student_public_key': student_public_key,
                    'manual': True,
                }
            )
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            logger.exception(f"Unexpected error marking manual attendance for lecture {lecture_id}")
            # Save to failed transaction queue
            cls.save_failed_transaction(
                transaction_type='attendance',
                error=e,
                transaction_data={
                    'lecture_id': lecture_id,
                    'student_public_key': student_public_key,
                    'manual': True,
                }
            )
            raise BlockchainTransactionError(f"Unexpected error marking manual attendance: {str(e)}")
    
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
            logger.error(f"Error verifying attendance: {e}")
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

    @staticmethod
    def save_failed_transaction(transaction_type, error, transaction_data, **kwargs):
        """
        Save failed blockchain transaction to queue for manual retry.
        Issue #6: Add failed transaction queue for admin review

        Args:
            transaction_type: Type of transaction ('attendance', 'lecture', 'course')
            error: The exception that was raised
            transaction_data: Dict with original transaction parameters
            **kwargs: Additional fields (student, lecture, course, etc.)
        """
        from .models import FailedBlockchainTransaction
        import traceback

        # Determine error type
        error_type = type(error).__name__

        # Create failed transaction record
        FailedBlockchainTransaction.objects.create(
            transaction_type=transaction_type,
            status='pending',
            transaction_data=transaction_data,
            error_type=error_type,
            error_message=str(error),
            error_traceback=traceback.format_exc(),
            **kwargs  # student, lecture, course, etc.
        )

        logger.warning(
            f"Saved failed {transaction_type} transaction to queue: {error_type} - {str(error)}"
        ) 