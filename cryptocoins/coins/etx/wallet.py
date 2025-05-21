import logging
import secrets
from django.conf import settings
from django.db import transaction
from web3 import Web3

from eth_account.account import Account
from core.consts.currencies import BlockchainAccount
from lib.cipher import AESCoderDecoder

log = logging.getLogger(__name__)


def create_etx_address():
    while 1:
        private_key = "0x" + secrets.token_hex(32)
        account = Account.from_key(private_key)
        encrypted_key = AESCoderDecoder(settings.CRYPTO_KEY).encrypt(private_key)
        decrypted_key = AESCoderDecoder(settings.CRYPTO_KEY).decrypt(encrypted_key)
        if decrypted_key.startswith('0x') and len(decrypted_key) == 66:
            break
    return account.address, encrypted_key


def create_new_etx_account() -> BlockchainAccount:
    address, encrypted_pk = create_etx_address()
    return BlockchainAccount(
        address=address,
        private_key=AESCoderDecoder(settings.CRYPTO_KEY).decrypt(encrypted_pk),
    )


@transaction.atomic
def get_or_create_etx_wallet(user_id, is_new=False):
    from core.models.cryptocoins import UserWallet
    from cryptocoins.coins.etx import ETX_CURRENCY

    wallet = UserWallet.objects.filter(
        user_id=user_id,
        currency=ETX_CURRENCY,
        blockchain_currency=ETX_CURRENCY,
    ).order_by('-id').first()

    if not is_new and wallet:
        return wallet

    address, encrypted_key = create_etx_address()

    wallet = UserWallet.objects.create(
        user_id=user_id,
        address=address,
        private_key=encrypted_key,
        currency=ETX_CURRENCY,
        blockchain_currency=ETX_CURRENCY
    )
    return wallet


def etx_wallet_creation_wrapper(user_id, is_new=False, **kwargs):
    from core.models.cryptocoins import UserWallet
    wallet = get_or_create_etx_wallet(user_id, is_new=is_new)
    return UserWallet.objects.filter(id=wallet.id)


def is_valid_etx_address(address):
    return Web3.is_address(address)
