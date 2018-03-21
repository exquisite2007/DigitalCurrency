
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
		self.name='bitfinex'
		self.PAIR_MAP={'BTC_ETH':'ETHBTC','BTC_LTC':'LTCBTC','BTC_USDT':'BTCUSD','ETC_USDT':'ETCUSD'}	
		self.CURRENT_PAIR=self.PAIR_MAP[pair]
		self.CURRENCY=[self.CURRENT_PAIR[:3],self.CURRENT_PAIR[-3:]]
		self.WALLET={}
		self.ORDER_BOOK={}
		self.TAKER_FEE=0.002
		self.ask_head_all=None
		self.bid_head_all=None
		self.ticker_value=None
	access_key=None
	secret_key=None
	async def order_book(self,trade_handler):
		while True:
			async with websockets.connect('wss://api.bitfinex.com/ws/2') as websocket:
				try:
					param={'event':'subscribe','channel':'book','symbol':self.CURRENT_PAIR,'prec':'P0','freq':'F0','len': '25'}
					await websocket.send(json.dumps(param))	
					while True:
						message = await websocket.recv()
						res=json.loads(message)
						if type(res) is not list:
							continue
						data=res[1]
						if len(data) >3:
							self.ORDER_BOOK['ask']={}
							self.ORDER_BOOK['bid']={}
							for item in data[25:25+BOOK_LIMIT]:#snapshot
								self.ORDER_BOOK['ask'][item[0]]=-item[1]
							for item in data[:BOOK_LIMIT]:#snapshot
								self.ORDER_BOOK['bid'][item[0]]=item[1]								
						elif len(data)==3:
							if data[2]>0:#bid
								if data[1]==0 and data[0] in self.ORDER_BOOK['bid']:
									del self.ORDER_BOOK['bid'][data[0]]
								else:
									self.ORDER_BOOK['bid'][data[0]]=data[2]
							else:
								if data[1]==0 and data[0] in self.ORDER_BOOK['ask']:
									del self.ORDER_BOOK['ask'][data[0]]
								else:
									self.ORDER_BOOK['ask'][data[0]]=-data[2]
						ask_head=min(self.ORDER_BOOK['ask'],key=lambda subItem:float(subItem))
						ask_head_volume=self.ORDER_BOOK['ask'][ask_head]
						bid_head=max(self.ORDER_BOOK['bid'],key=lambda subItem:float(subItem))
						bid_head_volume=self.ORDER_BOOK['bid'][bid_head]
						ask_head_all=ask_head+':'+str(ask_head_volume)
						bid_head_all=bid_head+':'+str(bid_head_volume)
						if ask_head_all != self.ask_head_all or bid_head_all != self.bid_head_all:
							self.ask_head_all=ask_head_all
							self.bid_head_all=bid_head_all
							await trade_handler()
				except Exception as e:
					self.ORDER_BOOK={}
					logger.error('ERROR happen in bitfinex connection:{}'.format(e))
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
			try:
				async with websockets.connect('wss://api.bitfinex.com/ws/2') as websocket:
				
					param={'event':'subscribe','channel':'ticker','symbol':self.CURRENT_PAIR}
					await websocket.send(json.dumps(param))	
					while True:
						message = await websocket.recv()
						res=json.loads(message)
						if type(res) is not list:
							continue
						data=res[1]
						if type(data) is not list:
							continue
						ask1=float(data[0])
						bid1=float(data[2])
						last=float(data[6])
						self.ticker_value=(ask1,bid1,last)
						await trade_handler()
			except Exception as e:
				self.ticker_value = None
				logger.error('ERROR happen in bitfinex connection:{}'.format(e))

async def test(ask1,bid1,last):
	print('test:{},{},{}'.format(ask1,bid1,last))
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
	loop.run_until_complete(util.ticker(test))
if __name__ == "__main__":
	sys.exit(main())

