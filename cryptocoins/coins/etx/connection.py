import logging
from collections import deque

from django.conf import settings
from django.core.cache import cache
from web3 import Web3
from web3.middleware import geth_poa_middleware

from lib.notifications import send_telegram_message

ETX_PROVIDERS_CACHE = 'ETX_PROVIDERS_CACHE'
ETX_RESPONSE_TIME_COUNTER_CACHE = 'ETX_RESPONSE_TIME_COUNTER'

log = logging.getLogger(__name__)


def set_etx_endpoints(endpoints: deque):
    cache.set(ETX_PROVIDERS_CACHE, endpoints)


def get_current_etx_endpoint():
    endpoints = cache.get(ETX_PROVIDERS_CACHE)
    if not endpoints:
        from cryptocoins.coins.etx import ETX_RPC_ENDPOINTS
        endpoints = deque(ETX_RPC_ENDPOINTS)
        set_etx_endpoints(endpoints)
    return endpoints[0]


def change_etx_endpoint(current):
    endpoints = cache.get(ETX_PROVIDERS_CACHE)
    if endpoints[0] == current:
        endpoints.rotate()
        set_etx_endpoints(endpoints)
    return endpoints[0]


def check_etx_response_time(w3, time_sec):
    counter = cache.get(ETX_RESPONSE_TIME_COUNTER_CACHE, 0)
    if time_sec >= 2.8:
        counter += 1
    else:
        counter = 0
    if counter >= 3:
        counter = 0
        w3.change_provider()
        send_telegram_message(f"ETX RPC slow, switching to {w3.provider.endpoint_uri}")
    cache.set(ETX_RESPONSE_TIME_COUNTER_CACHE, counter)


class Web3ETX(Web3):
    def __init__(self, *args, **kwargs):
        selected_provider = Web3.HTTPProvider(get_current_etx_endpoint())
        log.info(f'Using ETX provider {selected_provider.endpoint_uri}')
        super(Web3ETX, self).__init__(selected_provider, *args, **kwargs)

    def change_provider(self):
        new_provider = Web3.HTTPProvider(change_etx_endpoint(self.provider.endpoint_uri))
        self.manager = self.RequestManager(self, new_provider)
        self.middleware_onion.inject(geth_poa_middleware, layer=0)
        log.info(f'Changed ETX provider to {new_provider.endpoint_uri}')


def get_w3_etx_connection():
    w3 = Web3ETX()
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    return w3
