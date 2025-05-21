from cryptocoins.coins.etx.connection import get_w3_etx_connection
from cryptocoins.coins.etx.wallet import etx_wallet_creation_wrapper, is_valid_etx_address
from cryptocoins.utils.register import register_coin
from cryptocoins.coins import etx

ETX = 55
CODE = 'ETX'
DECIMALS = 18

ETX_CURRENCY = register_coin(
    currency_id=ETX,
    currency_code=CODE,
    address_validation_fn=is_valid_etx_address,
    wallet_creation_fn=etx_wallet_creation_wrapper,
    latest_block_fn=lambda currency: get_w3_etx_connection().eth.get_block_number(),
    blocks_diff_alert=50,
)

# Export constants
ETX_CHAIN_ID = etx.ETX_CHAIN_ID
ETX_RPC_ENDPOINTS = etx.ETX_RPC_ENDPOINTS
