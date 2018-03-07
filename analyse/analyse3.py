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

SELECT_SQL='select  diversion,timestamp from bookOrder where type=? '


def parse(pair,date):
    conn = sqlite3.connect('../data/orderbook_'+pair+'_'+date+'.db')
    freq='5S'
    cursor = conn.cursor()
    ex1_buy = pd.read_sql_query(SELECT_SQL, conn,params=(0,),index_col='timestamp')
    ex1_buy.index=pd.to_datetime(ex1_buy.index,unit='s')
    ex2_buy=pd.read_sql_query(SELECT_SQL, conn,params=(1,),index_col='timestamp')
    ex2_buy.index = pd.to_datetime(ex2_buy.index,unit='s')
    conn.close()

    # res_df=pd.concat([ex1_buy,ex2_buy],axis=1)
    # print(res_df)
    ex1_buy['diversion'].resample('600S').ohlc().plot()
    # ex1_buy.plot()
    plt.show()
       


    
    
  
    


def main(argv=None):
    parser = OptionParser()
    parser.add_option("-d", "--date", dest="date", help="select date")
    parser.add_option("-p", "--pair", dest="pair", help="set pair")
    parser.add_option("-m", "--mode", dest="mode", help="set direction")
    # set defaults
    parser.set_defaults(pair='LTC_USDT',date="2018-03-07",)



        # process options
    (opts, args) = parser.parse_args(argv)
    parse(opts.pair,opts.date)

    




if __name__ == "__main__":
    sys.exit(main())