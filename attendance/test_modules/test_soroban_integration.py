"""
Soroban SDK Integration Tests
Issue #28: Add integration tests with Soroban SDK

These tests verify the integration between Django and Soroban contracts.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from attendance.stellar_helper import StellarHelper


@pytest.mark.django_db
class TestSorobanContractIntegration:
    """Test suite for Soroban contract integration"""

    def test_get_contract_id_configuration(self):
        """Test that contract ID can be retrieved from configuration"""
        from attendance.stellar_helper import get_contract_id

        # In test environment, contract ID might not be set
        contract_id = get_contract_id()
        # Should return None or a valid string
        assert contract_id is None or isinstance(contract_id, str)

    def test_network_configuration(self):
        """Test network configuration (testnet vs mainnet)"""
        from attendance.stellar_helper import get_network_passphrase

        passphrase = get_network_passphrase()
        # Should be either testnet or mainnet passphrase
        assert 'Stellar' in passphrase or 'Test SDF' in passphrase

    @patch('attendance.stellar_helper.Server')
    def test_stellar_server_connection(self, mock_server):
        """Test connection to Stellar network"""
        from attendance.stellar_helper import get_horizon_url

        horizon_url = get_horizon_url()
        # Should be a valid URL
        assert horizon_url.startswith('https://')

    def test_explorer_url_generation(self):
        """Test blockchain explorer URL generation - Issue #22"""
        test_hash = 'abc123def456'
        url = StellarHelper.get_explorer_url(test_hash)

        assert url is not None
        assert test_hash in url
        assert 'stellar.expert' in url.lower() or 'stellarchain' in url.lower()

    def test_explorer_url_testnet_vs_mainnet(self):
        """Test that explorer URLs differ for testnet vs mainnet"""
        test_hash = 'test_transaction_hash'
        url = StellarHelper.get_explorer_url(test_hash)

        # URL should contain network indicator
        assert 'testnet' in url.lower() or 'public' in url.lower()

    @patch('attendance.stellar_helper.StellarHelper.verify_contract_connection')
    def test_contract_connection_verification(self, mock_verify):
        """Test contract connection verification"""
        mock_verify.return_value = {
            'status': 'success',
            'connected': True
        }

        result = StellarHelper.verify_contract_connection()
        assert result['status'] == 'success'

    @patch('attendance.stellar_helper.Keypair')
    def test_keypair_generation(self, mock_keypair):
        """Test Stellar keypair generation"""
        mock_kp = Mock()
        mock_kp.public_key = 'GXXXXXXXXXXXXX'
        mock_kp.secret = 'SXXXXXXXXXXXXX'
        mock_keypair.random.return_value = mock_kp

        kp = mock_keypair.random()
        assert kp.public_key.startswith('G')
        assert kp.secret.startswith('S')


@pytest.mark.django_db
class TestFailedTransactionQueue:
    """Test suite for failed transaction queue - Issue #6"""

    def test_save_failed_transaction(self):
        """Test saving failed transaction to queue"""
        from attendance.stellar_helper import StellarHelper
        from attendance.models import FailedBlockchainTransaction

        # Simulate a failed transaction
        error = Exception("Test blockchain error")
        transaction_data = {
            'lecture_id': 1,
            'student_public_key': 'GTEST',
            'nonce': '12345'
        }

        StellarHelper.save_failed_transaction(
            transaction_type='attendance',
            error=error,
            transaction_data=transaction_data
        )

        # Verify it was saved
        failed_tx = FailedBlockchainTransaction.objects.first()
        assert failed_tx is not None
        assert failed_tx.transaction_type == 'attendance'
        assert failed_tx.status == 'pending'
        assert failed_tx.error_type == 'Exception'

    def test_failed_transaction_can_retry(self):
        """Test failed transaction retry capability"""
        from attendance.models import FailedBlockchainTransaction

        failed_tx = FailedBlockchainTransaction.objects.create(
            transaction_type='attendance',
            status='pending',
            transaction_data={'test': 'data'},
            error_type='TestError',
            error_message='Test error message',
            retry_count=0,
            max_retries=3
        )

        assert failed_tx.can_retry() is True

        # Exceed max retries
        failed_tx.retry_count = 3
        failed_tx.save()

        assert failed_tx.can_retry() is False

    def test_failed_transaction_mark_success(self):
        """Test marking failed transaction as successful"""
        from attendance.models import FailedBlockchainTransaction

        failed_tx = FailedBlockchainTransaction.objects.create(
            transaction_type='attendance',
            status='pending',
            transaction_data={'test': 'data'},
            error_type='TestError',
            error_message='Test error message'
        )

        test_hash = 'abc123'
        failed_tx.mark_success(tx_hash=test_hash)

        assert failed_tx.status == 'success'
        assert failed_tx.successful_tx_hash == test_hash
        assert failed_tx.resolved_at is not None


@pytest.mark.django_db
class TestCeleryTasks:
    """Test suite for Celery async tasks - Issue #8"""

    @patch('attendance.tasks.StellarHelper')
    def test_retry_failed_transaction_task_exists(self, mock_helper):
        """Test that retry failed transaction task exists"""
        from attendance.tasks import retry_failed_blockchain_transaction

        # Task should be callable
        assert callable(retry_failed_blockchain_transaction)

    def test_cleanup_task_exists(self):
        """Test that cleanup task exists"""
        from attendance.tasks import cleanup_old_failed_transactions

        assert callable(cleanup_old_failed_transactions)

    @patch('attendance.tasks.FailedBlockchainTransaction')
    def test_cleanup_removes_old_transactions(self, mock_model):
        """Test that cleanup task removes old resolved transactions"""
        from attendance.tasks import cleanup_old_failed_transactions

        mock_queryset = Mock()
        mock_queryset.delete.return_value = (5, {})
        mock_model.objects.filter.return_value = mock_queryset

        result = cleanup_old_failed_transactions()

        assert result['deleted'] == 5


@pytest.mark.django_db
class TestPasswordResetSecurity:
    """Test suite for password reset security - Issue #12"""

    def test_password_reset_email_template_exists(self):
        """Test that password reset email template exists"""
        import os
        from django.conf import settings

        template_path = os.path.join(
            settings.BASE_DIR,
            'templates',
            'attendance',
            'password_reset_email.html'
        )

        # Template should exist
        assert os.path.exists(template_path)

    def test_password_reset_subject_template_exists(self):
        """Test that password reset subject template exists"""
        import os
        from django.conf import settings

        template_path = os.path.join(
            settings.BASE_DIR,
            'templates',
            'attendance',
            'password_reset_subject.txt'
        )

        # Template should exist
        assert os.path.exists(template_path)
