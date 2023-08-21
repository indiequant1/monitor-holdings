from toolkit.logger import Logger
from toolkit.fileutils import Fileutils
from login_get_kite import get_kite, remove_token
import pandas as pd
import sys
from time import sleep
import traceback

dir_path = "../../../"
logging = Logger(10)
fileutils = Fileutils()
holdings = dir_path + "holdings.csv"


try:
    perc = fileutils.get_lst_fm_yml("settings.yaml")['perc']
    broker = get_kite(api="bypass", sec_dir=dir_path)
    perc_col_name = f"perc_gr_{int(perc)}"
    logging.info("getting holdings for the day ...")
    resp = broker.kite.holdings()
    df = pd.DataFrame(resp)
    selected_cols = ['tradingsymbol', 'exchange', 'instrument_token',
                     'realised_quantity', 'close_price', 'average_price', 'pnl']
    df = df[selected_cols]
    df['cap'] = (df['realised_quantity'] * df['average_price']).astype(int)
    df['perc'] = ((df['pnl'] / df['cap']) * 100).round(2)
    cond = f"perc > {perc}"
    df[perc_col_name] = df.eval(cond)
    print(df)
    df.to_csv(holdings, index=False)
except Exception as e:
    remove_token(dir_path)
    print(traceback.format_exc())
    logging.error(f"{str(e)} unable to get holdings")
    sys.exit(1)

try:
    df = pd.read_csv(holdings)
    df['key'] = df['exchange'] + ":" + df['tradingsymbol']
    df.set_index('key', inplace=True)
    df = df[~(df == False).any(axis=1)]
    df.drop(['exchange', 'tradingsymbol', 'average_price',
            'pnl', 'cap', perc_col_name], axis=1, inplace=True)
    lst = df.index.to_list()
except Exception as e:
    print(traceback.format_exc())
    logging.error(f"{str(e)} while reading from csv")
    sys.exit(1)


def order_place(index, row):
    try:
        exchsym = index.split(":")
        logging.info(f"placing order for {index}, str{row}")
        order_id = broker.order_place(
            tradingsymbol=exchsym[1],
            exchange=exchsym[0],
            transaction_type='SELL',
            quantity=int(row['realised_quantity']),
            order_type='MARKET',
            product='CNC',
            variety='regular',
            trigger_price=0,
            price=0,
        )
        if order_id:
            logging.info("order {order_id} placed successfully")
            return True
    except Exception as e:
        print(traceback.format_exc())
        logging.error(f"{str(e)} while placing order")
        return False
    else:
        logging.error("error while generating order#")
        return False


try:
    while True:
        resp = broker.kite.ohlc(lst)
        dct = {k: {'ltp': v['last_price'], 'high': v['ohlc']['high']}
               for k, v in resp.items()}
        df['ltp'] = df.index.map(lambda x: dct[x]['ltp'])
        df['high'] = df.index.map(lambda x: dct[x]['high'])

        rows_to_remove = []
        for index, row in df.iterrows():
            if row['high'] > row['close_price'] and row['ltp'] < row['close_price']:
                is_placed = order_place(index, row)
                if is_placed:
                    rows_to_remove.append(index)

        # Remove rows based on the indices collected
        df.drop(rows_to_remove, inplace=True)
        print(df, "\n")
        sleep(3)
except Exception as e:
    remove_token(dir_path)
    print(traceback.format_exc())
    logging.error(f"{str(e)} in the main loop")
