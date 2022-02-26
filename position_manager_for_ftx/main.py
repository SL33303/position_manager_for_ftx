#%%
from position_manager_for_ftx.exchange.ftx.client import FtxClient
import time, datetime as dt, os, pandas as pd, numpy as np, matplotlib.pyplot as plt, asyncio

class Data:
    position_template = {
        'date': [],
        'timestamp': [],
        'market': [],
        'perpetual': [],
        'spot': [],
        'open_size': [],
        'average_entry': [],
        'last_price': [],
        'leverage': [],
        'realized_roe': [],
        'recent_roe': []
    }
    
class Authenticate:
    auth = {
        'account_nickname': {
            'key': '',
            'secret': '',
            'subaccount': None,
            'data': Data.position_template
            },
        'account_nickname2': {
            'key': '',
            'secret': '',
            'subaccount': None,
            'data': Data.position_template
            },
    }

def directory(module: str, name: str, file_type: str='.csv', library: str='/position_manager'):
    for dir_ in [module]:
        split_ = module.split('/')
        split_module_combined = ''
        for i in range(1, len(split_)):
            path = __file__.split(f'{library}')[0]
            split_module_combined = split_module_combined + f'/{split_[i]}'
            dir_ = path + library + split_module_combined
            try:
                os.mkdir(dir_)
                print(f'{dir_} created!')
            except: continue
    return path + library + f'{module}' + f'{name}' + file_type

class Position_Manager:
    def __init__(self):
        self.auth = Authenticate.auth
        self.ftx_client = lambda id_: FtxClient(api_key=self.auth[id_]['key'], api_secret=self.auth[id_]['secret'], subaccount_name=self.auth[id_]['subaccount'])
        self.client = {}
        self.wait_time_minutes = .05
        self.delay = int(self.wait_time_minutes * 60)
        for k in self.auth.keys():
            self.client[k] = self.ftx_client(k)
        self.public_client = FtxClient(api_key='', api_secret='', subaccount_name=None)
        self.dir = lambda id_: directory(f'/records/{id_}', f'/{id_}')
        self.market_data = {}

    def _list_all_markets(self):
            client = self.public_client
            markets = client.get_markets()
            for m in markets:
                self.market_data[m['name']] = {}
                for k in m.keys():
                    self.market_data[m['name']][k] = m[k]


    def _record(self, id_: str):
        client = self.client[id_]
        data = self.auth[id_]['data']
        date = dt.datetime.utcnow()
        ts = time.time()
        account = client.get_account_info()
        balances = client.get_balances()
        total_balance = pd.DataFrame(balances)['usdValue'].sum()
        for p in account['positions']:
            try:
                last = self.market_data[p['future']]['last']
                data['last_price'].append(last)
                data['date'].append(date)
                data['timestamp'].append(ts)
                data['market'].append(p['future'])
                data['perpetual'].append(True)
                data['spot'].append(False)
                data['open_size'].append(p['openSize'])
                data['average_entry'].append(p['entryPrice'])
                try:
                    data['leverage'].append((1 if p['openSize'] > 0 else -1) * p['collateralUsed']/total_balance)
                    data['realized_roe'].append(p['realizedPnl']/total_balance)
                    data['recent_roe'].append(p['unrealizedPnl']/total_balance)

                except:
                    data['leverage'].append(0)
                    data['realized_roe'].append(0)
                    data['recent_roe'].append(0)

            except: continue
        for b in balances:
            try:
                coin = b['coin'] + '/USD'
                try:
                    last = self.market_data[coin]['last']

                    total = b['total']
                    usd_value = b['usdValue']
                    try:
                        uroe = ((-1 if usd_value > 0 else 1) * usd_value - (total * last))/total_balance
                        lev = (total * last) * (1 + uroe * (1 if total > 0 else -1))/total_balance
                    except:
                        uroe = 0
                        lev = 0

                    data['date'].append(date)
                    data['timestamp'].append(ts)
                    data['market'].append(coin)
                    data['perpetual'].append(False)
                    data['spot'].append(True)
                    data['open_size'].append(total)
                    data['average_entry'].append(last * (1 + uroe * (1 if total > 0 else -1)))
                    data['last_price'].append(last)
                    try:
                        data['leverage'].append(lev/total_balance)
                        data['realized_roe'].append(uroe)
                        data['recent_roe'].append(uroe)
                    except:
                        data['leverage'].append(0)
                        data['realized_roe'].append(0)
                        data['recent_roe'].append(0)
                        
                except: pass

            except: continue
        try:
            pd.read_csv(self.dir(id_))
        except:
            file_ = open(self.dir(id_), 'a')
            for k in data.keys():
                if k != list(data.keys())[-1]:
                    file_.write(f'{k},')
                else:
                    file_.write(f'{k}\n')
        finally:
            file_ = open(self.dir(id_), 'a')
            for i in range(len(data['date'])):
                for k in data.keys():
                    if k != list(data.keys())[-1]:
                        file_.write(f'{data[k][i]},')
                    else:
                        file_.write(f'{data[k][i]}\n')
        self.auth[id_]['data'] = Data.position_template

    def _run(self):
        try:
            while True:
                for k in self.auth.keys():
                    self._list_all_markets()
                    self._record(k)
                for i in range(self.delay):
                    print(i/self.delay)
                    time.sleep(1)
        except(ConnectionAbortedError, ConnectionError, ConnectionRefusedError, ConnectionResetError, OSError, TimeoutError, BrokenPipeError):
            print('reconnecting...')
            time.sleep(5)
        except:
            raise

    def _get_data(self, id_: str):
        df = pd.read_csv(self.dir(id_))
        output = df.set_index(['market', 'timestamp'])
        output = output.sort_index()
        return output

    def _filter_data(self, id_: str, market: str):
        output = self._get_data(id_)
        return output.loc[market, ]

    def _plot_roe(self, id_: str, markets: list):
        fig, ax = plt.subplots(figsize=(15, 7))
        
        for m in markets:
            df = self._filter_data(id_, m)
            ret = (1 + df.last_price.pct_change() * df.leverage).cumprod()
            x, y = ret.index, ret
            ax.plot(x, y)
            ax.text(x[-1], y.iloc[-1], m, c='black')
        
        ax.set_title(id_)
        ax.set_facecolor('silver')
        plt.tight_layout()
        plt.show()


#%%        
if __name__ == '__main__':
    try: loop = asyncio.get_event_loop()
    except: loop = asyncio.get_running_loop()
    pm = Position_Manager()
    loop.run_until_complete(pm._run())
# %%
if __name__ == '__main__':
    pm = Position_Manager()
    pm._plot_roe('account_nickname', ['BTC/USD', 'ETH/USD', 'SOL/USD'])
    time.sleep(5)

# %%
