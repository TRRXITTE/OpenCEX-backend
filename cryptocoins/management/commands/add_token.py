import json
from string import printable
from urllib.parse import urlparse

from django.core.management.base import BaseCommand
from django.db.models import Max
from web3 import Web3

from core.consts.currencies import (
    BEP20_CURRENCIES, ERC20_CURRENCIES, TRC20_CURRENCIES, CURRENCIES_LIST,
    CRYPTO_ADDRESS_VALIDATORS, ERC20_MATIC_CURRENCIES, ETX20_CURRENCIES
)
from core.currency import Currency, CurrencyNotFound
from core.models import PairSettings, FeesAndLimits, WithdrawalFee
from core.models.facade import CoinInfo
from core.models.stats import InoutsStats
from core.models.inouts.pair import Pair, PairNotFound
from cryptocoins.data_sources.crypto import binance_data_source, kucoin_data_source
from cryptocoins.tokens_manager import read_tokens_file, write_tokens_file, get_tokens_backup_diffs, \
    restore_backup_file, register_tokens_and_pairs

TOKENS_BLOCKCHAINS_MAP = {
    'ETH': ERC20_CURRENCIES,
    'BNB': BEP20_CURRENCIES,
    'TRX': TRC20_CURRENCIES,
    'MATIC': ERC20_MATIC_CURRENCIES,
    'ETX': ETX20_CURRENCIES,
}

EXPLORERS_MAP = {
    'ETH': 'https://etherscan.io/',
    'BNB': 'https://bscscan.com/',
    'TRX': 'https://tronscan.org/',
    'MATIC': 'https://polygonscan.com/',
    'ETX': 'https://explorer.etxchain.com/',
}

HEADER = """ 
 000000\                                 000000\  00000000\ 00\   00\ 
00  __00\                               00  __00\ 00  _____|00 |  00 |
00 /  00 | 000000\   000000\  0000000\  00 /  \__|00 |      \\00\ 00  |
00 |  00 |00  __00\ 00  __00\ 00  __00\ 00 |      00000\     \\0000  / 
00 |  00 |00 /  00 |00000000 |00 |  00 |00 |      00  __|    00  00<  
00 |  00 |00 |  00 |00   ____|00 |  00 |00 |  00\ 00 |      00  /\\00\ 
 000000  |0000000  |\\0000000\ 00 |  00 |\\000000  |00000000\ 00 /  00 |
 \______/ 00  ____/  \_______|\__|  \__| \______/ \________|\__|  \__|
          00 |                                                        
          00 |                                                        
          \__|  

Hello! This is OpenCEX token adding setup. Please enter parameters for your token.
If you make a mistake when entering a parameter, don't worry, 
at the end of each parameter block you will have the opportunity 
to re-enter the parameters.

* is for the required field. 
"""

STEP1_HEADER = """
===========================================================
     STEP 1 OF 3. TOKEN BLOCKCHAIN INFO
===========================================================

Token symbol* - ticker symbol of the token (i.e. USDT)
Token blockchain symbol* - symbol of token's blockhain. 
    Supported only ETH(Ethereum), BNB(BSC), TRX(Tron), MATIC (Polygon), ETX (ETX Chain)
Token contract address* - token's contract address in blockchain.
    Enter address with upper case symbols
    (i.e. 0xdAC17F958D2ee523a2206206994597C13D831ec7)
Token contract decimals* - number of decimals in contract

-----------------------------------------------------------
"""

STEP2_HEADER = """
===========================================================
     STEP 2 OF 3. TOKEN PAIR INFO
===========================================================

Precisions for pair <ticker>-USDT* - numeric values from max to min, 
    separated by comma for groupping orderbook (i.e. 10,1,0.1,0.01)
Token custom price* - asked if there is no external 
    price (Binance, Kucoin). Set in USDT

-----------------------------------------------------------
"""

STEP3_HEADER = """
===========================================================
     STEP 3 OF 3. TOKEN INFO
===========================================================

Token name*: - name of token (i.e. Tether)
Token logo URL: - permalink to square logo in png or svg 
    (i.e. https://test.com/icon.svg)
Decimals for rounding*: - numeric value for rounding on
    trading and other pages. (i.e. 2 for 0.01 rounding)
Token index*: - token place in list of coins at wallet
    (i.e. 6). Default coins have 1...5 indexes.
CoinMarketCap link: - link to coin's CoinMarketCap page
Official site link: - link to coin's official page

-----------------------------------------------------------
"""

SPLITTER = """-----------------------------------------------------------"""


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('-r', '--revert', action='store_true',
                            default=False,
                            help="Restore tokens file backup and deletes previously created DB entries",
                            )

    def handle(self, *args, **options):
        is_revert = options.get('revert')
        if is_revert:
            revert()
            return

        print(HEADER)
        input('Press enter to continue...')

        all_tokens_data = read_tokens_file()

        # STEP 1. Token data
        print(STEP1_HEADER)
        yes_no = False
        while not yes_no:
            # common token data
            token_symbol = prompt('Token symbol* (i.e. USDT)').upper()
            blockchain_symbol = prompt('Token blockchain symbol* (i.e. ETH)', choices=[
                'ETH', 'BNB', 'TRX', 'MATIC', 'ETX',
            ])

            if is_token_exists(token_symbol, blockchain_symbol):
                print('[!] Token with this blockchain already added')
                return

            contract = prompt_contract(blockchain_symbol)
            decimals = prompt('Token contract decimals* (i.e. 18)', int)
            print(SPLITTER)
            yes_no = prompt_yes_no('IS EVERYTHING CORRECT?')

        token_currency_id = get_available_currency_id()

        only_blockchain_added = token_symbol in all_tokens_data

        if not only_blockchain_added:
            all_tokens_data[token_symbol] = {'id': token_currency_id, 'blockchains': {}, 'pairs': []}

        all_tokens_data[token_symbol]['blockchains'][blockchain_symbol] = {
            "contract": contract,
            "decimals": decimals
        }

        # new blockchain is added to the existing token
        if only_blockchain_added:
            write_tokens_file(json.dumps(all_tokens_data, indent=2))
            register_tokens_and_pairs()
            create_withdrawal_fee(token_symbol, blockchain_symbol)
            print('Token successfully added. Restart the backend to complete installation.')
            return

        # STEP 2. Pair data
        print(STEP2_HEADER)

        pair_to_usdt = f'{token_symbol}-USDT'
        is_price_external = binance_data_source.is_pair_exists(pair_to_usdt) or kucoin_data_source.is_pair_exists(
            pair_to_usdt)
        yes_no = False
        while not yes_no:
            precisions = prompt_precisions(token_symbol)
            if not is_price_external:
                custom_price = prompt(f'Token custom price*', arg_type=float)
            print(SPLITTER)
            yes_no = prompt_yes_no('IS EVERYTHING CORRECT?')

        pair_id = get_available_pair_id()
        all_tokens_data[token_symbol]["pairs"].append([pair_id, pair_to_usdt])
        write_tokens_file(json.dumps(all_tokens_data, indent=2))
        register_tokens_and_pairs()

        pair = Pair.get(pair_to_usdt)
        pair_settings = {'pair': pair, 'precisions': precisions}
        if is_price_external:
            pair_settings['price_source'] = PairSettings.PRICE_SOURCE_EXTERNAL
        else:
            pair_settings['price_source'] = PairSettings.PRICE_SOURCE_CUSTOM
            pair_settings['custom_price'] = custom_price
        PairSettings.objects.create(**pair_settings)

        # STEP 3. Token info
        if is_entry_exists(CoinInfo, {'currency': token_symbol}):
            print(f'[*] CoinInfo already exists for {token_symbol}')
        else:
            print(STEP3_HEADER)
            yes_no = False
            while not yes_no:
                token_name = prompt('Token name* (i.e. Tether):')
                logo = prompt('Token logo URL (i.e. https://test.com/icon.svg)', default='')
                display_decimals = prompt('Decimals for rounding* (i.e. 2)', int)
                index = prompt('Token index* (i.e. 6)')
                cmc_link = prompt('CoinMarketCap link', default='')
                off_link = prompt('Official site link', default='')
                print(SPLITTER)
                yes_no = prompt_yes_no('IS EVERYTHING CORRECT?')

            exp_link = EXPLORERS_MAP[blockchain_symbol]
            if off_link:
                try:
                    off_title = urlparse(off_link).netloc
                except:
                    off_title = off_link

            links = {}
            if cmc_link:
                links['cmc'] = {
                    'href': cmc_link,
                    'title': 'CoinMarketCap'
                }
            if exp_link:
                links['exp'] = {
                    'href': exp_link,
                    'title': 'Explorer'
                }
            if off_link:
                links['official'] = {
                    'href': off_link,
                    'title': off_title
                }
            CoinInfo.objects.create(
                currency=token_symbol,
                logo=logo,
                name=token_name,
                decimals=display_decimals,
                index=index,
                links=links
            )

        # ************FeesAndLimits**************
        if is_entry_exists(FeesAndLimits, {'currency': token_symbol}):
            print(f'[*] FeesAndLimits already exists')
        else:
            default_fees_and_limits = {
                'currency': token_symbol,
                'limits_deposit_min': 1.00000000,
                'limits_deposit_max': 1000000.00000000,
                'limits_withdrawal_min': 2.00000000,
                'limits_withdrawal_max': 10000.00000000,
                'limits_order_min': 1.00000000,
                'limits_order_max': 100000.00000000,
                'limits_code_max': 100000.00000000,
                'limits_accumulation_min': 1.00000000,
                'fee_deposit_address': 0,
                'fee_deposit_code': 0,
                'fee_withdrawal_code': 0,
                'fee_order_limits': 0.00100000,
                'fee_order_market': 0.00200000,
                'fee_exchange_value': 0.00200000,
            }
            FeesAndLimits.objects.create(**default_fees_and_limits)

        create_withdrawal_fee(token_symbol, blockchain_symbol)

        # ********* InoutsStats **************
        if is_entry_exists(InoutsStats, {'currency': token_symbol}):
            print(f'[*] InoutsStats already exists')
        else:
            InoutsStats.objects.create(
                currency=token_symbol,
            )
        print('Token successfully added. Restart the backend to complete installation.')


def revert():
    diff = get_tokens_backup_diffs()
    if not diff:
        print('[-] Revert is impossible')
        return
    if diff.token and not diff.blockchain:
        print('[*] CoinInfo, FeesAndLimits, WithdrawalFee, InoutsStats, PairSettings entries will be deleted')
        if is_entry_exists(CoinInfo, {'currency': diff.token}):
            CoinInfo.objects.filter(currency=diff.token).delete()

        if is_entry_exists(FeesAndLimits, {'currency': diff.token}):
            FeesAndLimits.objects.filter(currency=diff.token).delete()

        if is_entry_exists(WithdrawalFee, {'currency': diff.token}):
            WithdrawalFee.objects.filter(currency=diff.token).delete()

        if is_entry_exists(InoutsStats, {'currency': diff.token}):
            InoutsStats.objects.filter(currency=diff.token).delete()

        if is_entry_exists(PairSettings, {'pair': Pair.get(f'{diff.token}-USDT')}):
            PairSettings.objects.filter(pair=Pair.get(f'{diff.token}-USDT')).delete()

        if is_entry_exists(Pair, {'base': diff.token, 'quote': 'USDT'}):
            Pair.objects.filter(base=diff.token, quote='USDT').delete()

    elif diff.token and diff.blockchain:
        print('[*] WithdrawalFee entry will be deleted')
        if is_entry_exists(WithdrawalFee, {'currency': diff.token, 'blockchain_currency': diff.blockchain}):
            WithdrawalFee.objects.filter(currency=diff.token, blockchain_currency=diff.blockchain).delete()
    restore_backup_file()


def get_available_currency_id():
    return max(max(c[0] for c in CURRENCIES_LIST), 1000) + 1


def get_available_pair_id():
    return Pair.objects.aggregate(Max('id'))['id__max'] + 1


def is_token_exists(token_symbol, blockchain_symbol):
    try:
        Currency.get(token_symbol)
        return blockchain_symbol in TOKENS_BLOCKCHAINS_MAP and token_symbol in TOKENS_BLOCKCHAINS_MAP[blockchain_symbol]
    except CurrencyNotFound:
        return False


def is_entry_exists(model, filters):
    return model.objects.filter(**filters).exists()


def create_withdrawal_fee(token_symbol, blockchain_symbol):
    if is_entry_exists(WithdrawalFee, {'currency': token_symbol, 'blockchain_currency': blockchain_symbol}):
        return
    WithdrawalFee.objects.create(currency=token_symbol, blockchain_currency=blockchain_symbol)


def prompt(prompt_text, arg_type=str, default=None, choices=None):
    while True:
        if choices:
            prompt_str = f'{prompt_text} {choices} '
        else:
            prompt_str = f'{prompt_text} '

        if default is not None:
            prompt_str += f'(default: {default}) '

        response = input(prompt_str)
        if not response and default is not None:
            return default
        if arg_type == int:
            try:
                return int(response)
            except ValueError:
                print('Please enter a valid integer')
        elif arg_type == float:
            try:
                return float(response)
            except ValueError:
                print('Please enter a valid float number')
        else:
            if choices and response not in choices:
                print(f'Please enter one of the following choices: {choices}')
                continue
            if not response.strip():
                print('This field is required')
                continue
            return response.strip()


def prompt_yes_no(prompt_text):
    while True:
        response = input(f'{prompt_text} (y/n): ').lower()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print('Please enter y or n')


def prompt_contract(blockchain_symbol):
    while True:
        contract = input('Token contract address* (i.e. 0xdAC17F958D2ee523a2206206994597C13D831ec7): ').strip()
        if not contract:
            print('Contract address is required')
            continue
        validator = CRYPTO_ADDRESS_VALIDATORS.get(blockchain_symbol)
        if validator and not validator(contract):
            print('Invalid contract address format')
            continue
        return contract


def prompt_precisions(token_symbol):
    while True:
        precisions_str = input(f'Precisions for pair {token_symbol}-USDT* (comma separated, e.g. 10,1,0.1,0.01): ').strip()
        if not precisions_str:
            print('This field is required')
            continue
        try:
            precisions = [float(p.strip()) for p in precisions_str.split(',')]
            if not precisions:
                raise ValueError
            return precisions
        except ValueError:
            print('Please enter valid numeric values separated by commas')
