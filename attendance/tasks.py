"""
Celery Tasks for Asynchronous Blockchain Operations
Issue #8: Add asynchronous queue-based processing
"""
from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def retry_failed_blockchain_transaction(self, transaction_id):
    """
    Retry a failed blockchain transaction asynchronously.

    Args:
        transaction_id: ID of FailedBlockchainTransaction to retry

    Returns:
        dict: Result of retry attempt
    """
    from .models import FailedBlockchainTransaction
    from .stellar_helper import StellarHelper

    try:
        transaction = FailedBlockchainTransaction.objects.get(id=transaction_id)

        if not transaction.can_retry():
            logger.warning(f"Transaction {transaction_id} cannot be retried")
            return {'status': 'error', 'message': 'Cannot retry transaction'}

        # Update status
        transaction.status = 'retrying'
        transaction.last_retry_at = timezone.now()
        transaction.retry_count += 1
        transaction.save()

        # Attempt retry based on transaction type
        helper = StellarHelper()
        tx_data = transaction.transaction_data

        if transaction.transaction_type == 'attendance':
            # Retry attendance marking
            if tx_data.get('manual'):
                # Manual attendance requires teacher seed (not stored for security)
                logger.error(f"Cannot auto-retry manual attendance without teacher credentials")
                transaction.status = 'pending'
                transaction.save()
                return {'status': 'error', 'message': 'Manual intervention required'}
            else:
                # Regular attendance requires student seed (not stored for security)
                logger.error(f"Cannot auto-retry attendance without student credentials")
                transaction.status = 'pending'
                transaction.save()
                return {'status': 'error', 'message': 'Manual intervention required'}

        elif transaction.transaction_type == 'lecture':
            # Retry lecture creation (requires teacher seed)
            logger.error(f"Cannot auto-retry lecture creation without teacher credentials")
            transaction.status = 'pending'
            transaction.save()
            return {'status': 'error', 'message': 'Manual intervention required'}

        # If we get here, mark as pending for manual retry
        transaction.status = 'pending'
        transaction.save()
        return {'status': 'pending', 'message': 'Requires manual retry with credentials'}

    except FailedBlockchainTransaction.DoesNotExist:
        logger.error(f"Failed transaction {transaction_id} not found")
        return {'status': 'error', 'message': 'Transaction not found'}

    except Exception as e:
        logger.exception(f"Error retrying transaction {transaction_id}")

        # Retry the Celery task itself
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            # Mark transaction as failed after max retries
            if 'transaction' in locals():
                transaction.status = 'failed'
                transaction.resolved_at = timezone.now()
                transaction.save()
            return {'status': 'error', 'message': f'Max retries exceeded: {str(e)}'}


@shared_task
def process_blockchain_transaction_async(transaction_type, transaction_data):
    """
    Process a blockchain transaction asynchronously.

    This allows the web request to return immediately while the blockchain
    transaction is processed in the background.

    Args:
        transaction_type: Type of transaction ('attendance', 'lecture', etc.)
        transaction_data: Dict containing transaction parameters

    Returns:
        dict: Result of transaction
    """
    from .stellar_helper import StellarHelper

    logger.info(f"Processing async {transaction_type} transaction")

    try:
        helper = StellarHelper()

        if transaction_type == 'attendance':
            # Note: This is a placeholder. In practice, we need the student's seed
            # which should not be stored. This task is mainly for demonstration.
            logger.warning("Async attendance processing requires secure credential handling")
            return {'status': 'error', 'message': 'Not implemented - requires secure credentials'}

        return {'status': 'error', 'message': f'Unknown transaction type: {transaction_type}'}

    except Exception as e:
        logger.exception(f"Error in async {transaction_type} transaction")
        return {'status': 'error', 'message': str(e)}


@shared_task
def cleanup_old_failed_transactions():
    """
    Periodic task to clean up old resolved failed transactions.

    Runs daily to remove transactions that have been resolved for > 30 days.
    """
    from .models import FailedBlockchainTransaction
    from datetime import timedelta

    cutoff_date = timezone.now() - timedelta(days=30)

    deleted_count, _ = FailedBlockchainTransaction.objects.filter(
        status__in=['success', 'cancelled'],
        resolved_at__lt=cutoff_date
    ).delete()

    logger.info(f"Cleaned up {deleted_count} old failed transactions")
    return {'deleted': deleted_count}
