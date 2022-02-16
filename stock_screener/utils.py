# import json
import yfinance as yf
import pandas as pd
import boto3
import numpy as np
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from io import StringIO
import botocore
import ta
import json
import urllib.request
import urllib.parse
import plotly.graph_objects as go


def adjust_start(df, start_date):
    mask = (df["Date"] >= start_date)
    dfNew = df.loc[mask].copy(deep=True)
    dfNew.reset_index(drop=True, inplace=True)
    return dfNew


def read_stock_data_from_S3(bucket, stock):
    s3_client = boto3.client("s3")
    object_key = f"{stock}.csv"
    csv_obj = s3_client.get_object(Bucket=bucket, Key=object_key)
    body = csv_obj['Body']
    csv_string = body.read().decode('utf-8')
    df = pd.read_csv(StringIO(csv_string), index_col=[0], parse_dates=[0])

    return df


def get_current_tickers(bucket):
    s3 = boto3.client('s3')
    tickerFile = s3.get_object(Bucket=bucket, Key="Tickers.txt")
    tickers = tickerFile['Body'].read().decode('utf-8').split()

    return tickers


def add_ma(df, ma_short, ma_long, window_short, window_long):
    if ma_short == "SMA":
        colShort = f"SMA_{window_short}"
        df[colShort] = ta.trend.sma_indicator(df["Close"], window=window_short)
    else:
        colShort = f"EMA_{window_short}"
        df[colShort] = ta.trend.ema_indicator(df["Close"], window=window_short)

    if ma_long == "SMA":
        colLong = f"SMA_{window_long}"
        df[colLong] = ta.trend.sma_indicator(df["Close"], window=window_long)
    else:
        colLong = f"EMA_{window_long}"
        df[colLong] = ta.trend.ema_indicator(df["Close"], window=window_long)

    df["short_more_than_long"] = df[colShort] >= df[colLong]
    df["No_trend_change"] = df["short_more_than_long"].eq(df["short_more_than_long"].shift())
    df = df.reset_index()
    df.loc[0, "No_trend_change"] = True
    mask = (df["No_trend_change"] == False) & (df["short_more_than_long"] == True)
    df.loc[mask, "MA_Flag"] = "Buy"
    mask = (df["No_trend_change"] == False) & (df["short_more_than_long"] == False)
    df.loc[mask, "MA_Flag"] = "Sell"

    mask = df["short_more_than_long"] == True
    df["MA_Rec"] = "Sell"
    df.loc[mask, "MA_Rec"] = "Buy"

    return df, colShort, colLong


def add_psar(df, psar_af, psar_ma):
    if 'Date' not in df.columns:
        df = df.reset_index()
    df["Parabolic_SAR"] = ta.trend.PSARIndicator(df["High"], df["Low"], df["Close"], psar_af, psar_ma).psar()
    mask = df["Parabolic_SAR"] > df["Close"]
    df["PSAR_Rec"] = "Buy"
    df.loc[mask, "Parabolic_SAR_Rec"] = "Sell"

    return df


def add_adx(df, window_size, limit):
    if 'Date' not in df.columns:
        df = df.reset_index()
    df["ADX"] = ta.trend.ADXIndicator(df["High"], df["Low"], df["Close"], window=window_size).adx()
    mask = df["ADX"] > limit
    df["ADX_Rec"] = False
    df.loc[mask, "ADX_Rec"] = True

    return df


def add_srsi(df, window_size, smooth1, smooth2, overbought_limit, oversold_limit):
    if 'Date' not in df.columns:
        df = df.reset_index()
    df["Stochastic_RSI"] = ta.momentum.StochRSIIndicator(df["Close"], window=window_size,
                                                         smooth1=smooth1, smooth2=smooth2).stochrsi()
    df["Stochastic_RSI_Rec"] = "Wait"
    mask = df["Stochastic_RSI"] > overbought_limit
    df.loc[mask, "Stochastic_RSI_Rec"] = "Sell"
    mask = df["Stochastic_RSI"] < oversold_limit
    df.loc[mask, "Stochastic_RSI_Rec"] = "Buy"

    return df


def add_macd(df, window_slow, window_fast, smoothing_period):
    if 'Date' not in df.columns:
        df = df.reset_index()
    df["MACD"] = ta.trend.MACD(df["Close"], window_slow=window_slow, window_fast=window_fast,
                               window_sign=smoothing_period).macd()
    mask = df["MACD"] >= 0
    df["MACD_Rec"] = "Sell"
    df.loc[mask, "MACD_Rec"] = "Buy"

    return df


def add_days_since_change(df, col_name):
    mask = df[col_name].eq(df[col_name].shift())
    df["Change_Flag"] = np.where(mask, False, True)
    df.loc[0, "Change_Flag"] = False
    df["Days_Since_Change"] = None
    mask = (df["Change_Flag"] == True)
    df.loc[mask, "Days_Since_Change"] = 0
    for i in range(1, len(df)):
        a = df.loc[i - 1, "Days_Since_Change"]
        if (a is not None) & (df.loc[i, "Days_Since_Change"] != 0):
            df.loc[i, 'Days_Since_Change'] = df.loc[i - 1, 'Days_Since_Change'] + 1

    return df


def make_graph(df, ticker, signal_names, height, width):
    """(pd DataFrame, string, integer, integer) => string
    Takes in Pandas DataFrame with stock prices and additional calculations,
    stock ticker, desired height and width of the graph.
    Returns an HTML string representing the graph.
    """
    buttons = [{"count": 5, "label": "5D", "step": "day", "stepmode": "backward"},
               {"count": 1, "label": "1M", "step": "month", "stepmode": "backward"},
               {"count": 3, "label": "3M", "step": "month", "stepmode": "backward"},
               {"count": 6, "label": "6M", "step": "month", "stepmode": "backward"},
               {"count": 1, "label": "1Y", "step": "year", "stepmode": "backward"}, ]

    fig = go.Figure()

    fig.add_trace(go.Scatter(name=ticker, x=df["Date"], y=df["Close"]))

    for signalName in signal_names:
        fig.add_trace(go.Scatter(name=signalName, x=df["Date"], y=df[signalName]))

    fig.update_layout(title=f"{ticker} prices over the past year", template="seaborn",
                      legend={"orientation": "h", "xanchor": "left"},
                      xaxis={
                          "rangeselector": {
                              "buttons": buttons
                          }}, width=width, height=height,
                      )
    graph = fig.to_html(full_html=False)
    return graph
