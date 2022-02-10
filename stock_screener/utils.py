#import json
import yfinance as yf
import pandas as pd
import boto3
import numpy
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
    df = df.loc[mask]
    return df

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


def add_ma(df, ma_short, ma_long, window_short, window_long, start_date):
    if ma_short == "Simple Moving Average":
        colShort = f"SMA_{window_short}"
        df[colShort] = ta.trend.sma_indicator(df["Close"], window=window_short)
    else:
        colShort = f"EMA_{window_short}"
        df[colShort] = ta.trend.ema_indicator(df["Close"], window=window_short)

    if ma_long == "Simple Moving Average":
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
    df["Parabolic_SAR"] = ta.trend.PSARIndicator(df["High"], df["Low"], df["Close"], psar_af, psar_ma).psar()
    mask = df["Parabolic_SAR"] > df["Close"]
    df["PSAR_Rec"] = "Buy"
    df.loc[mask, "PSAR_Rec"] = "Sell"

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