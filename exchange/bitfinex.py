
import requests
import json
import hashlib
import hmac
import asyncio
import websockets
from time import time
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
class bitfinexUtil:
	def __init__(self,pair):
		self.PAIR_MAP={'BTC_ETH':'ETHBTC','BTC_LTC':'LTCBTC','BTC_USDT':'BTCUSD','ETC_USDT':'ETCUSD'}	
		self.CURRENT_PAIR=self.PAIR_MAP[pair]
		self.CURRENCY=[self.CURRENT_PAIR[:3],self.CURRENT_PAIR[-3:]]
		self.WALLET={}
		self.ORDER_BOOK={}
	access_key=None
	secret_key=None
	async def order_book(self,trade_handler):
		while True:
			async with websockets.connect('wss://api.bitfinex.com/ws/2') as websocket:
				try:
					param={'event':'subscribe','channel':'book','symbol':self.CURRENT_PAIR,'prec':'P0','freq':'F0','len': '15'}
					await websocket.send(json.dumps(param))	
					while True:
						message = await websocket.recv()
						res=json.loads(message)
						if type(res) is not list or type(res) is not list:
							continue
						if len(res) >3:
							for item in res[1][25:25+BOOK_LIMIT]:#snapshot
								self.ORDER_BOOK['ask'][item[0]]=-item[1]
							for item in res[1][:BOOK_LIMIT]:#snapshot
								self.ORDER_BOOK['bid'][item[0]]=item[1]								
						elif len(res)==3:
							if item[2]>0:#bid
								if item[1]==0 and item[0] in self.ORDER_BOOK['bid']:
									del self.ORDER_BOOK['bid'][item[0]]
								else:
									self.ORDER_BOOK['bid'][item[0]]=item[2]
							else:
								if item[1]==0 and item[0] in self.ORDER_BOOK['ask']:
									del self.ORDER_BOOK['ask'][item[0]]
								else:
									self.ORDER_BOOK['ask'][item[0]]=-item[2]
							
						await trade_handler()
				except Exception as e:
					self.ORDER_BOOK={}
					logger.error('ERROR happen in bitfinex connection:{}'.format(e))
					websocket.close()
async def test():
	print('nothing here')
def main(argv=None):
	parser = OptionParser()
	parser.add_option("-m", "--mode", dest="mode", help="0-wallet,1-buy,2-sell")
	parser.add_option("-r", "--rate", dest="rate", help="rate")
	parser.add_option("-a", "--amount", dest="amount", help="amount")
	parser.add_option("-p", "--pair", dest="pair", help="pair")
	parser.set_defaults(mode=0,pair='ETC_USDT')
	util = bitfinexUtil('ETC_USDT')

	
	# if 'bitfinex_access_key' not in os.environ:
	# 	return
	# util.access_key=os.environ['bitfinex_access_key']
	# util.secret_key=os.environ['bitfinex_secret_key']
	(opts, args) = parser.parse_args(argv)
	loop=asyncio.get_event_loop()
	loop.run_until_complete(util.order_book(test))
if __name__ == "__main__":
	sys.exit(main())

