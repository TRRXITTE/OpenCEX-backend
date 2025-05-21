from dataclasses import dataclass
from typing import List, Tuple, Union, Dict, Optional
from collections.abc import Callable

from core.currency import Currency, TokenParams, CoinParams


@dataclass
class BlockchainAccount:
    """
    Blockchain Account Info
    """
    address: str
    private_key: str
    public_key: Optional[str] = None
    redeem_script: Optional[str] = None


# ========== Core Currency Collections ==========

ALL_CURRENCIES: List[Currency] = []  # all Currency instances
CURRENCIES_LIST: List[Tuple[int, str]] = []

# ========== Token Maps Per Blockchain ==========
ERC20_CURRENCIES: Dict[Currency, TokenParams] = {}
TRC20_CURRENCIES: Dict[Currency, TokenParams] = {}
BEP20_CURRENCIES: Dict[Currency, TokenParams] = {}
ERC20_MATIC_CURRENCIES: Dict[Currency, TokenParams] = {}
ERC20_ETX_CURRENCIES: Dict[Currency, TokenParams] = {}  # ✅ ETX20 tokens on TRRXITTE chain

ALL_TOKEN_CURRENCIES: List[Currency] = []

# ========== Address Validators ==========
CRYPTO_ADDRESS_VALIDATORS: Union[
    Dict[Currency, Callable],                  # Coins
    Dict[Currency, Dict[str, Callable]],       # Tokens
    dict
] = {}

# ========== Wallet Creators ==========
CRYPTO_WALLET_CREATORS: Union[
    Dict[Currency, Callable],                  # Coins
    Dict[Currency, Dict[str, Callable]],       # Tokens
    dict
] = {}

# ========== Other Core Params ==========
CRYPTO_COINS_PARAMS: Dict[Currency, CoinParams] = {}
CRYPTO_WALLET_ACCOUNT_CREATORS: Dict[Currency, BlockchainAccount] = {}

# ========== Aliases / Notes ==========
# Used optionally for docs or UI mapping
# ERC20 = ETH network tokens
# ETX20 = ETX (TRRXITTE Ethereum) network tokens
