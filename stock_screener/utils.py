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


def add_sma(df, window_short, window_long):
    df[f"SMA_{window_short}"] = ta.trend.sma_indicator(df["Close"], window=window_short)
    df[f"SMA_{window_long}"] = ta.trend.sma_indicator(df["Close"], window=window_long)
    df["short_more_than_long"] = df[f"SMA_{window_short}"] >= df[f"SMA_{window_long}"]
    df["No_trend_change"] = df["short_more_than_long"].eq(df["short_more_than_long"].shift())
    df = df.reset_index()
    df.loc[0, "No_trend_change"] = True
    mask = (df["No_trend_change"] == False) & (df["short_more_than_long"] == True)
    df.loc[mask, "Flag"] = "Buy"
    mask = (df["No_trend_change"] == False) & (df["short_more_than_long"] == False)
    df.loc[mask, "Flag"] = "Sell"
    df["Days_since_change"] = None
    mask = (df["Flag"] == "Sell") | (df["Flag"] == "Buy")
    df.loc[mask, "Days_since_change"] = 0
    for i in range(1, len(df)):
        a = df.loc[i - 1, "Days_since_change"]
        if (a is not None) & (df.loc[i, "Days_since_change"] != 0):
            df.loc[i, 'Days_since_change'] = df.loc[i - 1, 'Days_since_change'] + 1

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