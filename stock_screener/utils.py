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
import requests


def adjust_start(df, start_date):
    mask = (df["Date"] >= start_date)
    dfNew = df.loc[mask].copy(deep=True)
    dfNew.reset_index(drop=True, inplace=True)
    return dfNew


def get_company_name_from_yf(ticker):
    """string => string
    Takes in a ticker as a string.
    Returns the matching company name found on yfinance.
    """

    ticker = yf.Ticker(ticker)
    tickerDetails = ticker.info
    try:
        name = tickerDetails['longName']
    except KeyError:
        name = tickerDetails['shortName']
    return name


def upload_csv_to_S3(bucket, df, file_name):
    csv_buffer = StringIO()
    df.to_csv(csv_buffer)
    s3_resource = boto3.resource('s3')
    result = s3_resource.Object(bucket, f"{file_name}.csv").put(Body=csv_buffer.getvalue())
    res = result.get('ResponseMetadata')

    if res.get('HTTPStatusCode') == 200:
        print('File Uploaded Successfully')
    else:
        print('File Not Uploaded')

    return None


def prepare_ticker_info_update(current_tickers_info, ticker, ticker_name):
    """(df, string, string) => df
   Takes in a string representing the name of the S3 bucket where current tickers are being stored
   and a list of new tickers that need to be added to the ticker information file on S3.
   Uploads an updated ticker information file to S3 as a csv file and returns the updated dataframe.
   """
    dt = {'Ticker': [ticker], 'Name': [ticker_name]}
    dfUpdate = pd.DataFrame(data=dt).set_index('Ticker')
    df = current_tickers_info.append(dfUpdate, ignore_index=False)

    return df


def read_csv_from_S3(bucket, file_name):
    s3_client = boto3.client("s3")
    object_key = f"{file_name}.csv"
    csv_obj = s3_client.get_object(Bucket=bucket, Key=object_key)
    body = csv_obj['Body']
    csv_string = body.read().decode('utf-8')
    df = pd.read_csv(StringIO(csv_string), header=[0, 1], index_col=[0], parse_dates=[0])

    return df


def stocks_tidy_up(df):
    df.columns = df.columns.to_flat_index()
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    df = df.swaplevel(axis=1).sort_index(axis=1)
    return df


def stock_tidy_up(df, ticker):
    newDF = df.copy(deep=True)
    columns = [(ticker, 'Open'), (ticker, 'High'), (ticker, "Low"), (ticker, "Close"), (ticker, "Adj Close"),
               (ticker, "Volume")]
    newDF.columns = pd.MultiIndex.from_tuples(columns)
    newDF = newDF.sort_index(axis=1)

    return newDF


def get_current_tickers_info(bucket):
    s3_client = boto3.client("s3")
    object_key = "TickersInfo.csv"
    csv_obj = s3_client.get_object(Bucket=bucket, Key=object_key)
    body = csv_obj['Body']
    csv_string = body.read().decode('utf-8')
    df = pd.read_csv(StringIO(csv_string), index_col=[0])

    return df


def add_ma(df, ma_short, ma_long, window_short, window_long):
    if ma_short == "SMA":
        colShort = f"SMA {window_short}"
        df[colShort] = ta.trend.sma_indicator(df["Close"], window=window_short)
    else:
        colShort = f"EMA {window_short}"
        df[colShort] = ta.trend.ema_indicator(df["Close"], window=window_short)

    if ma_long == "SMA":
        colLong = f"SMA {window_long}"
        df[colLong] = ta.trend.sma_indicator(df["Close"], window=window_long)
    else:
        colLong = f"EMA {window_long}"
        df[colLong] = ta.trend.ema_indicator(df["Close"], window=window_long)

    df["short_more_than_long"] = df[colShort] >= df[colLong]
    df["No_trend_change"] = df["short_more_than_long"].eq(df["short_more_than_long"].shift())
    df = df.reset_index()
    df.loc[0, "No_trend_change"] = True
    mask = (df["No_trend_change"] == False) & (df["short_more_than_long"] == True)
    df.loc[mask, "MA Flag"] = "Buy"
    mask = (df["No_trend_change"] == False) & (df["short_more_than_long"] == False)
    df.loc[mask, "MA Flag"] = "Sell"

    mask = df["short_more_than_long"] == True
    df["MA Rec"] = "Sell"
    df.loc[mask, "MA Rec"] = "Buy"

    return df, colShort, colLong


def add_psar(df, psar_af, psar_ma):
    if 'Date' not in df.columns:
        df = df.reset_index()
    df["Parabolic SAR"] = ta.trend.PSARIndicator(df["High"], df["Low"], df["Close"], psar_af, psar_ma).psar()
    mask = df["Parabolic SAR"] > df["Close"]
    df["PSAR Rec"] = "Buy"
    df.loc[mask, "Parabolic SAR Rec"] = "Sell"

    return df


def add_adx(df, window_size, limit):
    if 'Date' not in df.columns:
        df = df.reset_index()
    df["ADX"] = ta.trend.ADXIndicator(df["High"], df["Low"], df["Close"], window=window_size).adx()
    mask = df["ADX"] > limit
    df["ADX Rec"] = False
    df.loc[mask, "ADX Rec"] = True

    return df


def add_srsi(df, window_size, smooth1, smooth2, overbought_limit, oversold_limit):
    if 'Date' not in df.columns:
        df = df.reset_index()
    df["Stochastic RSI"] = ta.momentum.StochRSIIndicator(df["Close"], window=window_size,
                                                         smooth1=smooth1, smooth2=smooth2).stochrsi()
    df["Stochastic RSI Rec"] = "Wait"
    mask = df["Stochastic RSI"] > overbought_limit
    df.loc[mask, "Stochastic RSI Rec"] = "Sell"
    mask = df["Stochastic RSI"] < oversold_limit
    df.loc[mask, "Stochastic RSI Rec"] = "Buy"

    return df


def add_macd(df, window_slow, window_fast, smoothing_period):
    if 'Date' not in df.columns:
        df = df.reset_index()
    df["MACD"] = ta.trend.MACD(df["Close"], window_slow=window_slow, window_fast=window_fast,
                               window_sign=smoothing_period).macd()
    mask = df["MACD"] >= 0
    df["MACD Rec"] = "Sell"
    df.loc[mask, "MACD Rec"] = "Buy"

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


def format_float(number):
    """(float) => string
    Takes a number that needs to be formatted, returns a string formatted as a float with 2 decimal places
    """
    string = '{0:.2f}'.format(number)
    return string


def calculate_price_dif(newPrice, oldPrice):
    priceDif = newPrice - oldPrice
    percDif = format_float(priceDif / oldPrice * 100)

    return priceDif, percDif


def get_price_change(df):
    """(pd dfFrame) => (float, tuple)
    Takes in Pandas dfFrame with stock prices for a specific instrument,
    returns:
    1 - a float for the last closing price
    2 - a tuple:
        - a string showing the changes in price since previous trading day,
        - a colour name (red or green) to use in HTML template to display the change.
    """

    closingPrice = df["Close"].iloc[-1]
    previousPrice = df["Close"].iloc[-2]
    priceDif, percDif = calculate_price_dif(closingPrice, previousPrice)
    if priceDif > 0:
        sign = "+"
        color = "green"
    else:
        sign = ""
        color = "red"
    priceDif = format_float(priceDif)
    change = (f"{sign}{priceDif} USD  ({sign}{percDif}%)", color)
    return closingPrice, change


def get_date_within_df(df, dt):
    allDates = list(df["Date"])
    while dt not in allDates:
        dt = dt - pd.DateOffset(1)
    return dt

def get_previous_sma(df, sma_col, latest_date, no_of_days):
    reqDate = get_date_within_df(df, latest_date - pd.DateOffset(no_of_days))
    mask = df["Date"] == reqDate
    prevSma = list(df.loc[mask, sma_col])[0]
    return prevSma


