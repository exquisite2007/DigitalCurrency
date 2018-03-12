
import requests
import json
import hashlib
import hmac
import asyncio
import websockets
from time import time
import gzip
import sys
from optparse import OptionParser
try:
    #python2
    from urllib import urlencode
except ImportError:
    #python3
    from urllib.parse import urlencode
import logging
logger = logging.getLogger("deal")
BOOK_LIMIT=10
class huobiUtil:
	def __init__(self,pair):
		self.PAIR_MAP={'BTC_ETH':'ethbtc','BTC_LTC':'ltcbtc','BTC_USDT':'btcusdt','ETC_USDT':'etcusdt'}	
		self.CURRENT_PAIR=self.PAIR_MAP[pair]
		self.CURRENCY=[self.CURRENT_PAIR[:3],self.CURRENT_PAIR[3:]]
		self.WALLET={}
		self.ORDER_BOOK={}
		self.TAKER_FEE=0.002
		self.ask_head_all=None
		self.bid_head_all=None
	access_key=None
	secret_key=None

	async def order_book(self,trade_handler):
		while True:
			async with websockets.connect('wss://api.huobi.pro/ws') as websocket:
				try:
					param={'sub':'market.'+self.CURRENT_PAIR+'.depth.step0','id':'5201314'}
					await websocket.send(json.dumps(param))	
					while True:
						msg=await websocket.recv()
						message = json.loads(gzip.decompress(msg))	
						if 'ping' in message:
							await websocket.send(json.dumps({'pong':message['ping']}))
						else:
							print (message)
				except Exception as e:
					self.ORDER_BOOK={}
					logger.error('ERROR happen in huobi connection:{}'.format(e))
					websocket.close()
	def get_orderbook_head(self):
		if self.ask_head_all is None or self.bid_head_all is None:
			raise Exception(self.name,'Error in get_orderbook_head')
		else:
			ask_heads=self.ask_head_all.split(':')
			bid_heads=self.bid_head_all.split(':')
			return (float(ask_heads[0]),float(ask_heads[1]),float(bid_heads[0]),float(bid_heads[1]))
	async def ticker(self,trade_handler):
		while True:
			async with websockets.connect('wss://api.huobi.pro/ws') as websocket:
				try:
					param={'sub':'market.'+self.CURRENT_PAIR+'.detail','id':'5201314'}
					await websocket.send(json.dumps(param))	
					while True:
						msg=await websocket.recv()
						message = json.loads(gzip.decompress(msg).decode("utf-8") )	
						if 'ping' in message:
							await websocket.send(json.dumps({'pong':message['ping']}))
						else:
							print (message)
				except Exception as e:
					logger.error('ERROR happen in huobi connection:{}'.format(e))
					websocket.close()

async def test():
	print('nothing here:{}'.format('larla'))
def main(argv=None):
	parser = OptionParser()
	parser.add_option("-p", "--pair", dest="pair", help="pair")
	parser.set_defaults(pair='ETC_USDT')
	
	util = huobiUtil('ETC_USDT')
	
	# if 'bitfinex_access_key' not in os.environ:
	# 	return
	# util.access_key=os.environ['bitfinex_access_key']
	# util.secret_key=os.environ['bitfinex_secret_key']
	(opts, args) = parser.parse_args(argv)
	loop=asyncio.get_event_loop()
	loop.run_until_complete(util.ticker(test))
if __name__ == "__main__":
	sys.exit(main())

