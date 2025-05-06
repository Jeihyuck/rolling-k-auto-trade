# rolling_k_auto_trade_api/main.py - FastAPI Entry Point for Auto Trading System
from fastapi import FastAPI
from fastapi import APIRouter
from datetime import datetime
import pandas as pd

from rolling_k_auto_trade_api.strategies import run_rebalance_for_date, auto_trade_on_rebalance, check_sell_conditions, generate_performance_report
from rolling_k_auto_trade_api.orders import router as order_router, get_order_status
from rolling_k_auto_trade_api.dashboard import dashboard_summary

app = FastAPI()
app.include_router(order_router)

@app.get("/rebalance/{date}")
def get_rebalance(date: str):
    return run_rebalance_for_date(date)

@app.get("/rebalance/latest")
def get_latest():
    from datetime import datetime
    import pandas as pd
    from rolling_k_auto_trade_api.strategies import run_rebalance_for_date

    # 오늘 날짜 기준 이번 달 1일
    today = pd.to_datetime(datetime.today().replace(day=1))
    date_str = today.strftime('%Y-%m-%d')

    return run_rebalance_for_date(date_str)


@app.post("/rebalance/run/{date}")
def trigger_rebalance_and_trade(date: str):
    return auto_trade_on_rebalance(date)

@app.post("/sell/check")
def sell_check():
    return check_sell_conditions()

@app.get("/order/status")
def order_status():
    return get_order_status()

@app.get("/dashboard")
def get_dashboard():
    return dashboard_summary()

@app.get("/report")
def get_report():
    return generate_performance_report()
