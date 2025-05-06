# rolling_k_auto_trade_api/strategies.py
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json, os
from rolling_k_auto_trade_api.orders import log_order, TRADE_STATE

K_RANGE = np.arange(0.1, 1.01, 0.05)
FEE = 0.0015
INVEST_UNIT = 1000000

LOG_DIR = "./rolling_k_auto_trade_api/logs"

def get_rolling_k_signals(code, start_train, end_train, start_test, end_test):
    try:
        df = fdr.DataReader(code, start_train, end_test)
        df.index = pd.to_datetime(df.index)
        train = df[start_train:end_train]
        test = df[start_test:end_test]
        if len(train) < 15 or len(test) < 5:
            return None

        best_k, best_ret = 0, -np.inf
        for k in K_RANGE:
            temp = train.copy()
            temp['range'] = temp['High'].shift(1) - temp['Low'].shift(1)
            temp['target'] = temp['Open'] + temp['range'] * k
            temp['buy_signal'] = temp['High'] > temp['target']
            temp['buy_price'] = np.where(temp['buy_signal'], temp['target'], np.nan)
            temp['sell_price'] = temp['Close']
            temp['strategy_return'] = np.where(
                temp['buy_signal'],
                (temp['sell_price'] - temp['buy_price']) / temp['buy_price'] - FEE,
                0
            )
            final_ret = (1 + temp['strategy_return'].fillna(0)).cumprod().iloc[-1] - 1
            if final_ret > best_ret:
                best_ret = final_ret
                best_k = k

        test['range'] = test['High'].shift(1) - test['Low'].shift(1)
        test['target'] = test['Open'] + test['range'] * best_k
        test['buy_signal'] = test['High'] > test['target']
        test['buy_price'] = np.where(test['buy_signal'], test['target'], np.nan)
        test['sell_price'] = test['Close']
        test['strategy_return'] = np.where(
            test['buy_signal'],
            (test['sell_price'] - test['buy_price']) / test['buy_price'] - FEE,
            0
        )
        test['cumulative'] = (1 + test['strategy_return'].fillna(0)).cumprod()
        final_ret = (test['cumulative'].iloc[-1] - 1) * 100
        mdd = ((test['cumulative'] - test['cumulative'].cummax()) / test['cumulative'].cummax()).min() * 100
        wins = (test['strategy_return'] > 0).sum()
        total = test['strategy_return'].notnull().sum()
        win_rate = wins / total if total > 0 else 0

        return {
            'best_k': best_k,
            'final_return': round(final_ret, 2),
            'mdd': round(mdd, 2),
            'win_rate': round(win_rate * 100, 2),
            'buy_signals': test[test['buy_signal']]
        }
    except:
        return None

import pandas as pd
import numpy as np
import FinanceDataReader as fdr

from rolling_k_auto_trade_api.orders import log_order, TRADE_STATE
from datetime import datetime
from typing import List

def run_rebalance_for_date(date_input):
    if date_input == "latest":
        raise ValueError("Invalid string literal 'latest' passed. Use actual date string like '2024-04-01'.")

    rebalance_date = pd.to_datetime(date_input)
    fee = 0.0015
    k_values = np.arange(0.1, 1.01, 0.05)
    rebalance_results = []

    # 시총 상위 50개 코스닥 종목
    kosdaq = fdr.StockListing('KOSDAQ')
    top50 = kosdaq.sort_values(by='Marcap', ascending=False).head(50)
    tickers = list(zip(top50['Code'], top50['Name']))

    # 리밸런싱 기준일 1개월 전 ~ 기준일까지
    start_train = (rebalance_date - pd.DateOffset(months=1)).strftime('%Y-%m-%d')
    end_train = (rebalance_date - pd.DateOffset(days=1)).strftime('%Y-%m-%d')
    start_test = rebalance_date.strftime('%Y-%m-%d')
    end_test = (rebalance_date + pd.DateOffset(months=1) - pd.DateOffset(days=1)).strftime('%Y-%m-%d')

    pool = []
    for code, name in tickers:
        try:
            df = fdr.DataReader(code, start_train, end_test)
            df.index = pd.to_datetime(df.index)
            train = df[(df.index >= start_train) & (df.index <= end_train)].copy()
            test = df[(df.index >= start_test) & (df.index <= end_test)].copy()
            if len(train) < 15 or len(test) < 5:
                continue

            best_k, best_ret = 0, -np.inf
            for k in k_values:
                temp = train.copy()
                temp['range'] = temp['High'].shift(1) - temp['Low'].shift(1)
                temp['target'] = temp['Open'] + temp['range'] * k
                temp['buy_signal'] = temp['High'] > temp['target']
                temp['buy_price'] = np.where(temp['buy_signal'], temp['target'], np.nan)
                temp['sell_price'] = temp['Close']
                temp['strategy_return'] = np.where(
                    temp['buy_signal'],
                    (temp['sell_price'] - temp['buy_price']) / temp['buy_price'] - fee,
                    0
                )
                temp['cumulative_return'] = (1 + temp['strategy_return'].fillna(0)).cumprod() - 1
                final_ret = temp['cumulative_return'].iloc[-1]
                if final_ret > best_ret:
                    best_ret = final_ret
                    best_k = k

            test['range'] = test['High'].shift(1) - test['Low'].shift(1)
            test['target'] = test['Open'] + test['range'] * best_k
            test['buy_signal'] = test['High'] > test['target']
            test['buy_price'] = np.where(test['buy_signal'], test['target'], np.nan)
            test['sell_price'] = test['Close']
            test['strategy_return'] = np.where(
                test['buy_signal'],
                (test['sell_price'] - test['buy_price']) / test['buy_price'] - fee,
                0
            )
            test['cumulative'] = (1 + test['strategy_return'].fillna(0)).cumprod()
            if len(test['cumulative']) == 0:
                continue
            mdd = ((test['cumulative'] - test['cumulative'].cummax()) / test['cumulative'].cummax()).min() * 100
            wins = (test['strategy_return'] > 0).sum()
            total = test['strategy_return'].notnull().sum()
            win_rate = wins / total if total > 0 else 0
            final_ret = (test['cumulative'].iloc[-1] - 1) * 100

            if (final_ret > 0) and (win_rate > 0.2) and (mdd > -30):
                pool.append({
                    '리밸런싱시점': start_test,
                    '티커': code,
                    '종목명': name,
                    '최적k': best_k,
                    '수익률(%)': round(final_ret, 2),
                    'MDD(%)': round(mdd, 2),
                    '승률(%)': round(win_rate * 100, 2)
                })
        except:
            continue

    pool_df = pd.DataFrame(pool).sort_values('수익률(%)', ascending=False).head(20)
    if len(pool_df) > 0:
        pool_df['포트비중(%)'] = round(100 / len(pool_df), 2)
    else:
        pool_df['포트비중(%)'] = 0

    return pool_df.to_dict(orient="records")


def auto_trade_on_rebalance(date_str):
    candidates = run_rebalance_for_date(date_str)
    results = []
    for stock in candidates:
        quantity = int(INVEST_UNIT // stock['수익률(%)']) if stock['수익률(%)'] != 0 else 1
        order = {
            "code": stock['code'],
            "name": stock['name'],
            "buy_price": 1000,  # placeholder, 실제 시세 연동 필요
            "quantity": quantity,
            "signal_date": date_str,
            "timestamp": datetime.now().isoformat()
        }
        log_order(order, "buy")
        TRADE_STATE[stock['code']] = order
        results.append(order)
    return results

def check_sell_conditions():
    results = []
    for code, info in list(TRADE_STATE.items()):
        price_now = 1050  # placeholder, 실제 실시간가 필요
        entry = info['buy_price']
        change = (price_now - entry) / entry * 100
        if change >= 5 or change <= -5:
            sell = {
                "code": code,
                "name": info['name'],
                "sell_price": price_now,
                "sell_date": datetime.now().strftime('%Y-%m-%d'),
                "reason": "익절" if change >= 5 else "손절"
            }
            log_order(sell, "sell")
            del TRADE_STATE[code]
            results.append(sell)
    return results

def generate_performance_report():
    try:
        buy_path = os.path.join(LOG_DIR, "buy_orders.log")
        sell_path = os.path.join(LOG_DIR, "sell_orders.log")
        if not os.path.exists(buy_path) or not os.path.exists(sell_path):
            return {"message": "No data"}

        with open(buy_path) as f:
            buys = [json.loads(line) for line in f]
        with open(sell_path) as f:
            sells = [json.loads(line) for line in f]

        returns = []
        for b in buys:
            match = next((s for s in sells if s['code'] == b['code'] and s['sell_date'] >= b['signal_date']), None)
            if match:
                ret = (match['sell_price'] - b['buy_price']) / b['buy_price'] * 100
                returns.append({"code": b['code'], "return": round(ret, 2), "buy": b['buy_price'], "sell": match['sell_price']})

        avg_ret = round(sum(r['return'] for r in returns) / len(returns), 2) if returns else 0
        return {"returns": returns, "average_return": avg_ret, "count": len(returns)}
    except Exception as e:
        return {"error": str(e)}
