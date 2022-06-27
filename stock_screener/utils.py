from io import StringIO

from dateutil.relativedelta import relativedelta
from datetime import date, datetime
from typing import Tuple

import boto3
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import ta
import yfinance as yf

constructorFields = ['ma', 'maS', 'maL', 'maWS', 'maWL', 'psar', 'psarAF', 'psarMA', 'adx', 'adxW', 'adxL', 'srsi',
                     'srsiW', 'srsiSm1', 'srsiSm2', 'srsiOB', 'srsiOS', 'macd', 'macdF', 'macdS', 'macdSm']


def adjust_start(df: pd.DataFrame, start_date: datetime) -> pd.DataFrame:
    """Creates a copy of current dataframe with starting date matching the requirements"""

    mask = (df["Date"] >= start_date)
    dfNew = df.loc[mask]  # .copy()
    dfNew.reset_index(drop=True, inplace=True)
    return dfNew


def get_company_details_from_yf(ticker: str) -> Tuple[str, str, str]:
    """Returns the matching company name, sector and country found on yfinance."""

    ticker = yf.Ticker(ticker)
    tickerDetails = ticker.info
    try:
        name = tickerDetails['longName']
    except KeyError:
        try:
            name = tickerDetails['shortName']
        except KeyError:
            name = "Full company name not available"
    try:
        sector = tickerDetails['sector']
    except KeyError:
        sector = None
    try:
        country = tickerDetails['country']
    except KeyError:
        country = None

    return name, sector, country


def upload_csv_to_S3(bucket: str, df: pd.DataFrame, file_name: str) -> None:
    """Converts dataframe  to CSV format and uploads it to S3"""
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


def prepare_ticker_info_update(current_tickers_info: pd.DataFrame, ticker: str, ticker_name: str, sector: str,
                               country: str) -> pd.DataFrame:
    """Adds information for a new ticker to the existing tickers details dataframe"""
    dt = {'Ticker': [ticker], 'Name': [ticker_name], 'Sector': [sector], 'Country': [country]}
    dfUpdate = pd.DataFrame(data=dt).set_index('Ticker')
    df = pd.concat([current_tickers_info, dfUpdate])
    return df


def read_csv_from_S3(bucket: str, file_name: str) -> pd.DataFrame:
    """Reads stock data from the S3 bucket indicated and returns a tidied up DataFrame."""
    s3_client = boto3.client("s3")
    object_key = f"{file_name}.csv"
    csv_obj = s3_client.get_object(Bucket=bucket, Key=object_key)
    body = csv_obj['Body']
    csv_string = body.read().decode('utf-8')
    df = pd.read_csv(StringIO(csv_string), header=[0, 1], index_col=[0], parse_dates=[0])
    return df


def stock_tidy_up(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Prepares stock data for upload on S3"""
    newDF = df.copy(deep=True)
    columns = [(ticker, 'Open'), (ticker, 'High'), (ticker, "Low"), (ticker, "Close"), (ticker, "Adj Close"),
               (ticker, "Volume")]
    newDF.columns = pd.MultiIndex.from_tuples(columns)
    newDF = newDF.sort_index(axis=1)
    return newDF


def get_saved_stocks_details() -> pd.DataFrame:
    """Prepares a locally saved csv file with tickers details for processing."""
    df = pd.read_csv("stock_screener/Tickers_details.csv")
    df.set_index("Ticker", inplace=True)
    return df


def add_days_since_change(df: pd.DataFrame, col_name: str) -> pd.DataFrame:
    """Takes in a dataframe and the name of the column in the dataframe that needs to be analysed.
    Returns an updated dataframe with a "Days_Since_Change" column added that shows
    the number of days since the value in the column indicated changed"""
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


def make_graph(df: pd.DataFrame, ticker: str, signal_names: list, height: int, width: int,
               srsi_overbought_limit: float = None, srsi_oversold_limit: float = None,
               adx_limit: int = None) -> Tuple[str, str, str, str]:
    """Takes in:
        - Pandas DataFrame with stock prices and additional calculations
        - stock ticker
        - names of the DataFrame columns to be plotted
        - desired height and width of the graph
    Returns an HTML string representing the graph.
    """
    buttons = [{"count": 5, "label": "5D", "step": "day", "stepmode": "backward"},
               {"count": 1, "label": "1M", "step": "month", "stepmode": "backward"},
               {"count": 3, "label": "3M", "step": "month", "stepmode": "backward"},
               {"count": 6, "label": "6M", "step": "month", "stepmode": "backward"},
               {"count": 1, "label": "1Y", "step": "year", "stepmode": "backward"}, ]

    limitLine = dict(color='#CA3435', width=2)
    graph1List = []
    srsiGraph = False
    adxGraph = False
    macdGraph = False
    for elt in signal_names:
        if elt.startswith("SMA") or elt.startswith("EMA") or elt == "Parabolic SAR":
            graph1List.append(elt)
        elif elt == "Stochastic RSI":
            srsiGraph = True
        elif elt == "ADX":
            adxGraph = True
        elif elt == "MACD":
            macdGraph = True

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(name=ticker, x=df["Date"], y=df["Close"], line=dict(color="#325C84", width=2)))
    for signalName in graph1List:
        if signalName == "Parabolic SAR":

            fig1.add_trace(go.Scatter(name=signalName, x=df["Date"], y=df[signalName], mode="markers", marker=dict(
                color='#99103d', size=4)))
        else:
            fig1.add_trace(go.Scatter(name=signalName, x=df["Date"], y=df[signalName], mode="lines", line=dict(
                width=3)))

    if "Buy" in df.columns:
        fig1.add_trace(
            go.Scatter(name="Buy signals", x=df["Date"], y=df["Buy"], mode="markers", marker_symbol="x", marker=dict(
                color='#1601FF', size=8)))
    if "Sell" in df.columns:
        fig1.add_trace(
            go.Scatter(name="Sell signals", x=df["Date"], y=df["Sell"], mode="markers", marker_symbol="x", marker=dict(
                color='#CC0200', size=8)))

    fig1.update_layout(title=f"{', '.join(['Stock Price'] + graph1List)} over the past year", template="seaborn",
                       legend={"orientation": "h", "xanchor": "left"},
                       xaxis={
                           "rangeselector": {
                               "buttons": buttons
                           }}, width=width, height=height,
                       font=dict(
                           family="Open Sans, sans-serif",
                           size=13,
                           color="#333333",
                       ), xaxis_range=[df["Date"].min(), df["Date"].max()]
                       )
    graph1 = fig1.to_html(full_html=False)

    if not adxGraph:
        graph2 = None
    else:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(name="ADX", x=df["Date"], y=df["ADX"], mode="lines", line=dict(
            width=2, color='#346602')))
        fig2.add_shape(type='line',
                       x0=df["Date"].min(), y0=adx_limit, x1=df["Date"].max(), y1=adx_limit,
                       line=limitLine, xref='x', yref='y')

        fig2.update_layout(title="ADX over the past year", template="seaborn",
                           legend={"orientation": "h", "xanchor": "left"},
                           xaxis={
                               "rangeselector": {
                                   "buttons": buttons
                               }}, width=width, height=height / 1.5,
                           )
        graph2 = fig2.to_html(full_html=False)

    if not srsiGraph:
        graph3 = None
    else:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(name="Stochastic RSI", x=df["Date"], y=df["Stochastic RSI"], mode="lines", line=dict(
            width=2, color='#188399')))

        fig3.add_shape(type='line',
                       x0=df["Date"].min(), y0=srsi_overbought_limit, x1=df["Date"].max(), y1=srsi_overbought_limit,
                       line=limitLine, xref='x', yref='y')
        fig3.add_shape(type='line', name="Oversold Limit",
                       x0=df["Date"].min(), y0=srsi_oversold_limit, x1=df["Date"].max(), y1=srsi_oversold_limit,
                       line=limitLine, xref='x', yref='y')
        fig3.update_layout(title="Stochastic RSI over the past year", template="seaborn",
                           legend={"orientation": "h", "xanchor": "left"},
                           xaxis={
                               "rangeselector": {
                                   "buttons": buttons
                               }}, width=width, height=height / 1.5,

                           )
        graph3 = fig3.to_html(full_html=False)

    if not macdGraph:
        graph4 = None
    else:
        fig4 = go.Figure()
        fig4.add_trace(
            go.Scatter(name="MACD", x=df["Date"], y=df["MACD"], mode="lines", line=dict(width=2, color="#058093")))

        fig4.update_layout(title="MACD over the past year", template="seaborn",
                           legend={"orientation": "h", "xanchor": "left"},
                           xaxis={
                               "rangeselector": {
                                   "buttons": buttons
                               }}, width=width, height=height / 1.5,
                           )
        graph4 = fig4.to_html(full_html=False)

    return graph1, graph2, graph3, graph4


def format_float(number: float) -> str:
    """Takes a number that needs to be formatted, returns a string formatted as a float with 2 decimal places."""
    string = '{0:.2f}'.format(number)
    return string


def calculate_price_dif(new_price, old_price):
    """(float/integer, float/integer => float/integer, string
    Takes an old price and a new price, returns the difference as a number
    as well as percentage of the old price"""
    price_dif = new_price - old_price
    perc_dif = format_float(price_dif / old_price * 100)
    return price_dif, perc_dif


def get_date_within_df(df, dt):
    """(pd DataFrame, timestamp) => (timestamp)
        Takes in Pandas DataFrame with a "Date" column and a timestamp for the date that needs to be located.
        Returns the original timestamp if it is found in the "Date" column,
        otherwise returns the closest earlier date
        """
    if "Date" in df.columns:
        col = df["Date"]
    else:
        col = df.index
    allDates = list(col)

    while dt not in allDates:
        if dt > col.min():
            dt = dt - pd.DateOffset(1)
        else:
            return None
    return dt


def get_start_dates(num_months_back):
    endDate = date.today()
    displayStartDate = endDate + relativedelta(months=-num_months_back)
    calculationsStartDate = pd.Timestamp(displayStartDate + relativedelta(months=-12))
    displayStartDateDatetime = datetime.combine(displayStartDate, datetime.min.time())
    return calculationsStartDate, displayStartDateDatetime


def get_previous_sma(df, sma_col, no_of_days):
    """(pd DataFrame, string, timestamp, integer) => (float)
        Takes in Pandas DataFrame, name of teh Simple Moving Average column in the dataframe (such as "SMA 15")
        with a "Date" column and a timestamp for the date that needs to be located.
        Returns the original timestamp if it is found in the "Date" column,
        otherwise returns the closest earlier date
    """
    latest_date = df["Date"].max()
    reqDate = get_date_within_df(df, latest_date - pd.DateOffset(no_of_days))
    if reqDate is None:
        return None
    else:
        mask = df["Date"] == reqDate
        prevSma = list(df.loc[mask, sma_col])[0]
        return prevSma


def backtest_signal(df, format_outcome=True, days_to_buy=0, days_to_sell=0, buy_price_adjustment=0,
                    sell_price_adjustment=0):
    """(pd DataFrame, boolean, integer, integer, integer, integer, """
    flags = ['Buy', 'Sell']
    columnsBacktest = ["Old_Index", "Date", "Close", "Final Rec", "Change_Flag", "Days_Since_Change"]
    backTest = df.loc[(df['Days_Since_Change'] == 0) & df['Final Rec'].isin(flags)].copy(deep=True)
    backTest.reset_index(drop=False, inplace=True)  # change
    backTest.rename(columns={"index": "Old_Index"}, inplace=True)
    backTest = add_days_since_change(backTest, "Final Rec")
    backTestClean = backTest.loc[backTest["Change_Flag"].isin([True]), columnsBacktest]
    if backTestClean.empty:
        return 0, None
    else:
        backTestClean.reset_index(drop=True, inplace=True)
        backTestClean["Price After Delay"] = np.NaN
        backTestClean["Adjusted Price After Delay"] = np.NaN

        backTestClean["Profit/Loss"] = 0

        start = 0
        if backTestClean.loc[start, "Final Rec"] == "Sell":
            start += 1

        max_index = df.index.max()

        for i in range(start, len(backTestClean)):

            rec = backTestClean.loc[i, "Final Rec"]

            if rec == "Sell":
                dfIndexAdjusted = backTestClean.loc[i, "Old_Index"] + days_to_sell
                if dfIndexAdjusted <= max_index:
                    unadjustedPrice = df.loc[dfIndexAdjusted, "Close"]
                    backTestClean.loc[i, "Price After Delay"] = unadjustedPrice
                    backTestClean.loc[i, "Adjusted Price After Delay"] = \
                        unadjustedPrice - sell_price_adjustment * unadjustedPrice / 10000

                    backTestClean.loc[i, 'Profit/Loss'] = (backTestClean.loc[i, 'Adjusted Price After Delay'] -
                                                           backTestClean.loc[i - 1, "Adjusted Price After Delay"]) / \
                                                          backTestClean.loc[i - 1, "Adjusted Price After Delay"] * 100

            elif rec == "Buy":
                dfIndexAdjusted = backTestClean.loc[i, "Old_Index"] + days_to_buy
                if dfIndexAdjusted <= max_index:
                    unadjustedPrice = df.loc[dfIndexAdjusted, "Close"]
                    backTestClean.loc[i, "Price After Delay"] = unadjustedPrice
                    backTestClean.loc[i, "Adjusted Price After Delay"] \
                        = unadjustedPrice + buy_price_adjustment * unadjustedPrice / 10000

        backTestClean.set_index("Date", inplace=True)

        backTestClean.dropna(subset=['Price After Delay', 'Adjusted Price After Delay'], inplace=True)
        if backTestClean.empty:
            return 0, None

        outcome = calc_average_percentage(backTestClean["Profit/Loss"])

        if format_outcome:
            outcome = str(round(outcome, 2)) + "%"

        backTestClean["Profit/Loss"] = backTestClean["Profit/Loss"].apply(lambda x: (format_float(x)) + " %")
        backTestClean["Close"] = backTestClean["Close"].apply(lambda x: format_float(x))
        backTestClean["Price After Delay"] = backTestClean["Price After Delay"].apply(lambda x: format_float(x))
        backTestClean["Adjusted Price After Delay"] = backTestClean["Adjusted Price After Delay"].apply(
            lambda x: format_float(x))

        # for col_title in ["Close", "Price After Delay", "Adjusted Price After Delay"]:
        # backTestClean[col_title] = backTestClean[col_title].apply(lambda x: format_float(x))

        return outcome, backTestClean


def check_for_sma_column(df):
    """Checks if the dataframe has a column starting with 'SMA'
    (Simple Moving Average column)"""
    for column in df.columns:
        if column.startswith("SMA"):
            return column
        return None


def add_sma_col(df):
    """Adds SMA """
    df["Table SMA"] = ta.trend.sma_indicator(df["Close"], window=15)
    column = "Table SMA"
    return df, column


def prepare_signal_table(signal_dict):
    signalData = []
    signalHeaders = []
    if signal_dict['ma']:
        signalData += [signal_dict['ma'],
                       signal_dict['maS'],
                       signal_dict['maL'],
                       signal_dict['maWS'],
                       signal_dict['maWL']]
        signalHeaders += ["Moving Average", "Moving Average Type (Short)", "Moving Average Type (Long)",
                          "Moving Average - Short Window Length", "Moving Average - Long Window Length"]

    if signal_dict['psar']:
        signalData += [signal_dict['psar'],
                       signal_dict['psarAF'],
                       signal_dict['psarMA']]
        signalHeaders += ["Parabolic SAR", "Parabolic SAR - Acceleration Factor",
                          "Parabolic SAR - Maximum Acceleration"]

    if signal_dict['adx']:
        signalData += [signal_dict['adx'],
                       signal_dict['adxW'],
                       signal_dict['adxL']]
        signalHeaders += ["ADX", "ADX Term", "ADX Limit"]

    if signal_dict['srsi']:
        signalData += [signal_dict['srsi'],
                       signal_dict['srsiW'],
                       signal_dict['srsiSm1'],
                       signal_dict['srsiSm2'],
                       signal_dict['srsiOB'],
                       signal_dict['srsiOS']]
        signalHeaders += ["Stochastic RSI", "Stochastic RSI - Term", "Stochastic RSI - Smooth 1",
                          "Stochastic RSI - Smooth 2", "Stochastic RSI - Overbought Limit",
                          "Stochastic RSI - Oversold Limit"]

    if signal_dict['macd']:
        signalData += [signal_dict['macd'],
                       signal_dict['macdS'],
                       signal_dict['macdF'],
                       signal_dict['macdSm']]
        signalHeaders += ["MACD", "MACD Slow", "MACD Fast", "MACD Smoothing Period"]

    signalTable = pd.DataFrame([signalData], columns=signalHeaders).transpose().reset_index()

    signalTable = signalTable.to_html(col_space=[400, 100], classes=["table", "signal_table"],
                                      bold_rows=False, justify="left", header=False, index=False)

    return signalTable


def calc_average_percentage(perc_iterable):
    result = 1
    for v in perc_iterable:
        adj_v = (v + 100) / 100
        result *= adj_v
    return round((result * 100 - 100), 2)


def check_and_add_sma(df):
    smaCol = check_for_sma_column(df)
    if not smaCol:
        df, smaCol = add_sma_col(df)
    return df, smaCol


def compare_signals(signal_class_instance, signal_dict):
    signal_class_instance_dict = vars(signal_class_instance)
    for field in constructorFields:
        if signal_class_instance_dict[field] != signal_dict[field]:
            return False
    return True
