"""
Django management command to verify Stellar network configuration
and provide migration guidance for mainnet deployment.
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from attendance.stellar_helper import StellarHelper
import sys


class Command(BaseCommand):
    help = 'Check Stellar network configuration and provide mainnet migration guidance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verify-connection',
            action='store_true',
            help='Verify connection to Stellar network',
        )
        parser.add_argument(
            '--show-config',
            action='store_true',
            help='Display current Stellar configuration',
        )
        parser.add_argument(
            '--mainnet-checklist',
            action='store_true',
            help='Show mainnet migration checklist',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Stellar Network Configuration ===\n'))

        # Show current configuration
        if options['show_config'] or not any(options.values()):
            self._show_config()

        # Verify connection
        if options['verify_connection']:
            self._verify_connection()

        # Show mainnet checklist
        if options['mainnet_checklist']:
            self._show_mainnet_checklist()

    def _show_config(self):
        """Display current Stellar configuration"""
        network = "TESTNET" if settings.STELLAR_TESTNET else "MAINNET"
        network_style = self.style.WARNING if settings.STELLAR_TESTNET else self.style.ERROR

        self.stdout.write(f"Network: {network_style(network)}")
        self.stdout.write(f"Horizon URL: {settings.STELLAR_HORIZON_URL}")
        self.stdout.write(f"Soroban RPC URL: {settings.STELLAR_RPC_URL}")

        if settings.STELLAR_CONTRACT_ID:
            self.stdout.write(f"Contract ID: {settings.STELLAR_CONTRACT_ID}")
        else:
            self.stdout.write(self.style.WARNING("Contract ID: Not configured"))

        self.stdout.write("")

    def _verify_connection(self):
        """Verify connection to Stellar network"""
        self.stdout.write("\nVerifying connection to Stellar network...")

        try:
            result = StellarHelper.verify_contract_connection()

            if result['status'] == 'success':
                self.stdout.write(self.style.SUCCESS(f"✓ {result['message']}"))
            elif result['status'] == 'partial':
                self.stdout.write(self.style.WARNING(f"⚠ {result['message']}"))
            else:
                self.stdout.write(self.style.ERROR(f"✗ {result['message']}"))
                sys.exit(1)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Connection failed: {str(e)}"))
            sys.exit(1)

        self.stdout.write("")

    def _show_mainnet_checklist(self):
        """Show mainnet migration checklist"""
        self.stdout.write(self.style.SUCCESS('\n=== Mainnet Migration Checklist ===\n'))

        if not settings.STELLAR_TESTNET:
            self.stdout.write(self.style.ERROR("⚠️  WARNING: You are already on MAINNET!\n"))

        checklist = [
            ("Security Audit", "Complete comprehensive security audit of all smart contracts"),
            ("Test Coverage", "Ensure 100% test coverage for all critical paths"),
            ("Load Testing", "Perform load testing with expected production traffic"),
            ("Backup Strategy", "Implement robust backup and disaster recovery procedures"),
            ("Monitoring", "Set up monitoring and alerting for blockchain transactions"),
            ("Rate Limiting", "Implement rate limiting to prevent abuse"),
            ("Error Handling", "Verify all error paths are properly handled"),
            ("Documentation", "Update all documentation with mainnet configuration"),
            ("Contract Deployment", "Deploy contracts to mainnet and verify functionality"),
            ("Environment Variables", "Update .env with mainnet configuration:"),
        ]

        for i, (item, description) in enumerate(checklist, 1):
            self.stdout.write(f"{i}. {self.style.WARNING(item)}")
            self.stdout.write(f"   {description}\n")

        # Show example mainnet configuration
        self.stdout.write(self.style.SUCCESS("\n=== Example Mainnet Configuration ===\n"))
        self.stdout.write("Add to your .env file:")
        self.stdout.write(self.style.HTTP_INFO("""
STELLAR_NETWORK=mainnet
STELLAR_HORIZON_URL=https://horizon.stellar.org
STELLAR_RPC_URL=https://soroban.stellar.org
STELLAR_CONTRACT_ID=<your-mainnet-contract-id>
STELLAR_ADMIN_SECRET=<your-mainnet-admin-secret>
        """))

        # Warning about Friendbot
        self.stdout.write(self.style.ERROR("\n⚠️  IMPORTANT WARNINGS:\n"))
        self.stdout.write("1. Friendbot is NOT available on mainnet")
        self.stdout.write("2. All accounts must be funded with real XLM")
        self.stdout.write("3. All transactions will cost real XLM")
        self.stdout.write("4. Smart contract deployments are irreversible")
        self.stdout.write("5. Thoroughly test on testnet before mainnet deployment\n")

        # Show network detection
        if settings.STELLAR_TESTNET:
            self.stdout.write(self.style.SUCCESS("✓ Currently on testnet - safe for testing\n"))
        else:
            self.stdout.write(self.style.ERROR("✗ Currently on MAINNET - use with caution!\n"))
