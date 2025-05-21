from typing import List
from web3 import Web3
from django.conf import settings

from cryptocoins.monitoring.base_monitor import BaseMonitor
from lib.helpers import to_decimal


class EtxMonitor(BaseMonitor):
    CURRENCY = 'ETX'
    BLOCKCHAIN_CURRENCY = 'ETX'
    ACCUMULATION_TIMEOUT = 60 * 10
    DELTA_AMOUNT = to_decimal(0.01)
    SAFE_ADDRESS = settings.ETX_SAFE_ADDR
    OFFSET_SECONDS = 16

    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(settings.TRRXITTE_RPC_URL))

    def get_address_transactions(self, address, from_block=None, to_block=None) -> List:
        """
        Fetch native ETX transactions by scanning blocks and filtering txs involving address.
        from_block and to_block allow incremental scanning.
        """
        address = self.w3.toChecksumAddress(address)
        latest_block = self.w3.eth.blockNumber if to_block is None else to_block
        start_block = from_block or (latest_block - 1000)  # scan last 1000 blocks if not specified

        tx_list = []
        for block_num in range(start_block, latest_block + 1):
            block = self.w3.eth.getBlock(block_num, full_transactions=True)
            for tx in block.transactions:
                if tx['to'] and (tx['to'].lower() == address.lower() or tx['from'].lower() == address.lower()):
                    tx_list.append(tx)
        return tx_list
