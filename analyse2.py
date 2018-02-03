#!/usr/bin/env python
# encoding: utf-8
'''
base.analyze -- shortdesc

base.analyze is a description

It defines classes_and_methods

@author:     johnny

@copyright:  2018 organization_name. All rights reserved.

@license:    license

@contact:    lihongwei.bupt@gmail.com
@deffield    updated: 2018-01-06
'''

import sys
import os
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt

from optparse import OptionParser

__all__ = []
__version__ = 0.1
__date__ = '2018-01-06'
__updated__ = '2018-01-06'

SELECT_SQL='select timestamp,ask1,bid1 from bookOrder where exchange=? '
wallet=[[1.0,0.0],[0.0,35]]
x={'ok':0,'poloniex':0,'profit':0,'direction':0,'ok_c':0,'polo_c':0}

def exchange(serial_item):
    #ok buy
    ok_buy_profit=serial_item[1]-serial_item[2]-(serial_item[1]*0.001+serial_item[2]*0.0025) 
    # if ok_buy_profit >0.24809:
    if ok_buy_profit >0.12:
        x['ok_c']+=1
        if  x['direction']==0:
            x['ok']+=1
            x['profit']+=ok_buy_profit
            x['direction']=1
            print('buy:'+str(ok_buy_profit))
        return
    ok_sell_profit=serial_item[3]-serial_item[0]-(serial_item[3]*0.001+serial_item[0]*0.0025)
    if ok_sell_profit > -0.02:
        x['polo_c']+=1
        if  x['direction']==1 :
            x['poloniex']+=1
            x['profit']+=ok_sell_profit
            x['direction']=0
            print('sell:'+str(ok_sell_profit))
        return


def parse(date,mode):
    conn = sqlite3.connect('orderbook_'+date+'.db')
    freq='5S'
    cursor = conn.cursor()
    # resLst=cursor.execute(SELECT_SQL, (exchange,pair))
    okex_df = pd.read_sql_query(SELECT_SQL, conn,params=('okex',),index_col='timestamp')
    # df = pd.read_sql_table('trades',conn,)
    okex_df.index=pd.to_datetime(okex_df.index/1000,unit='s')
    # print(df['price'].resample('1H').ohlc().tail())
    # print(df['amount'].resample('1H').sum().tail())
    # print(df['price'].resample('1H').mean().tail())
    # okex_mean_serial= okex_df['price'].resample(freq).mean()
    # okex_mean_serial.name='okex'



    poloniex_df=pd.read_sql_query(SELECT_SQL, conn,params=('poloniex',),index_col='timestamp')
    poloniex_df.index = pd.to_datetime(poloniex_df.index/1000,unit='s')
    conn.close()
    if mode==1:
        res_df = pd.concat([okex_df,poloniex_df],axis=1)
        res_df.apply(exchange,axis=1)
        print(x)
    else:

        profit_ok_sell=okex_df['bid1']-poloniex_df['ask1']-(okex_df['bid1']*0.001+poloniex_df['ask1']*0.0015)
        # first=okex_df['bid1']-poloniex_df['ask1']
        profit_ok_sell.name='ok sell and poloniex buy'
        profit_ok_buy=poloniex_df['bid1']-okex_df['ask1']-(okex_df['ask1']*0.001+poloniex_df['bid1']*0.0015)
        # second=poloniex_df['bid1']-okex_df['ask1']
        profit_ok_buy.name='poloniex sell and ok buy'
        res_df=pd.concat([profit_ok_sell,profit_ok_buy],axis=1)
        res_df.plot()

        # cost_ok_sell=okex_df['bid1']*0.001+poloniex_df['ask1']*0.0015
        # cost_ok_sell.name='cost_ok_sell'
        # cost_ok_buy=okex_df['ask1']*0.001+poloniex_df['bid1']*0.0015
        # cost_ok_buy='cost_ok_buy'
        # # res_df=pd.concat([cosk_ok_sell,cost_ok_buy],axis=1)
        # res_df=cost_ok_sell/profit_ok_sell
        # res_df.plot()
       
        plt.show()
  


    
    
  
    


def main(argv=None):
    parser = OptionParser()
    parser.add_option("-d", "--date", dest="date", help="select date")
    parser.add_option("-t", "--toward", dest="toward", help="set direction")
    parser.add_option("-m", "--mode", dest="mode", help="set direction")
    # set defaults
    parser.set_defaults(toward=0,date="2018-01-25",mode=1)



        # process options
    (opts, args) = parser.parse_args(argv)
    x['direction']=int(opts.toward)
    parse(opts.date,int(opts.mode))

    




if __name__ == "__main__":
    sys.exit(main())