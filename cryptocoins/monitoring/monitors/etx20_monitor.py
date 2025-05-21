from typing import List
from web3 import Web3
from django.conf import settings

from cryptocoins.monitoring.base_monitor import BaseMonitor
from lib.helpers import to_decimal

ERC20_TRANSFER_EVENT_SIG = Web3.keccak(text="Transfer(address,address,uint256)").hex()


class Etx20BaseMonitor(BaseMonitor):
    CURRENCY = ''
    BLOCKCHAIN_CURRENCY = 'ETX'
    ACCUMULATION_TIMEOUT = 60 * 10
    DELTA_AMOUNT = to_decimal(0.01)
    SAFE_ADDRESS = settings.ETX_SAFE_ADDR
    OFFSET_SECONDS = 16

    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(settings.TRRXITTE_RPC_URL))

    def get_address_transactions(self, address, from_block=None, to_block=None) -> List:
        """
        Fetch ETX20 token transfers from TRRXITTE blockchain logs by filtering Transfer events of the token contract.
        """
        address = self.w3.toChecksumAddress(address)
        latest_block = self.w3.eth.blockNumber if to_block is None else to_block
        start_block = from_block or (latest_block - 1000)  # scan last 1000 blocks if not specified

        # Token contract address needs to be set for this monitor
        token_address = self.w3.toChecksumAddress(self.CURRENCY)

        filter_params = {
            "fromBlock": start_block,
            "toBlock": latest_block,
            "address": token_address,
            "topics": [ERC20_TRANSFER_EVENT_SIG, None, None]
        }

        logs = self.w3.eth.getLogs(filter_params)
        filtered_logs = []
        for log in logs:
            # Decode the 'from' and 'to' from topics and check if address involved
            from_addr = self.w3.toChecksumAddress('0x' + log['topics'][1].hex()[-40:])
            to_addr = self.w3.toChecksumAddress('0x' + log['topics'][2].hex()[-40:])
            if address in [from_addr, to_addr]:
                filtered_logs.append(log)

        return filtered_logs


class Et20Monitor(Etx20BaseMonitor):
    # Here CURRENCY is the contract address of the ETX20 token on TRRXITTE chain
    CURRENCY = settings.ETX20_TOKEN_CONTRACT_ADDRESS
