from io import StringIO

import boto3
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import ta
import yfinance as yf

constructorFields = ['ma', 'maS', 'maL', 'maWS', 'maWL', 'psar', 'psarAF', 'psarMA', 'adx', 'adxW', 'adxL', 'srsi',
                     'srsiW', 'srsiSm1', 'srsiSm2', 'srsiOB', 'srsiOS', 'macd', 'macdF', 'macdS', 'macdSm']


def adjust_start(df, start_date):
    """(pd DataFrame, date as datetime.datetime) => pd DataFrame
    Creates a copy of current dataframe with starting date matching the requirements"""

    mask = (df["Date"] >= start_date)
    dfNew = df.loc[mask]  # .copy()
    dfNew.reset_index(drop=True, inplace=True)
    return dfNew


def get_company_details_from_yf(ticker):
    """(string) => (string, string, string)
    Takes in a ticker as a string.
    Returns the matching company name found on yfinance.
    """

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


def upload_csv_to_S3(bucket, df, file_name):
    """(string, pd DataFrame), string => None
    converts dataframe  to CSV format and uploads it to S3"""
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


def prepare_ticker_info_update(current_tickers_info, ticker, ticker_name, sector, country):
    """(df, string, string) => df
   Takes in a string representing the name of the S3 bucket where current tickers are being stored
   and a list of new tickers that need to be added to the ticker information file on S3.
   Uploads an updated ticker information file to S3 as a csv file and returns the updated dataframe.
   """
    dt = {'Ticker': [ticker], 'Name': [ticker_name], 'Sector': [sector], 'Country': [country]}
    dfUpdate = pd.DataFrame(data=dt).set_index('Ticker')
    df = current_tickers_info.append(dfUpdate, ignore_index=False)
    df.drop_duplicates(subset=None, keep='first', inplace=True, ignore_index=False)

    return df


def read_csv_from_S3(bucket, file_name):
    """(string, string) => pd DataFrame
    Takes in the name of the S3 bucket and the name of the csv file to be read,
    returns decoded CSV file as pd DataFrame"""
    s3_client = boto3.client("s3")
    object_key = f"{file_name}.csv"
    csv_obj = s3_client.get_object(Bucket=bucket, Key=object_key)
    body = csv_obj['Body']
    csv_string = body.read().decode('utf-8')
    df = pd.read_csv(StringIO(csv_string), header=[0, 1], index_col=[0], parse_dates=[0])
    return df


def stocks_tidy_up(df):
    """(pd DataFrame) => pd DataFrame
    Takes in the DataFrame with data for multiple stocks,
    prepares the data for upload on S3"""
    df.columns = df.columns.to_flat_index()
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    df = df.swaplevel(axis=1).sort_index(axis=1)
    return df


def stock_tidy_up(df, ticker):
    """(pd DataFrame, string) => pd DataFrame
    Takes in the DataFrame with data for one stock,
    prepares the data for upload on S3"""
    newDF = df.copy(deep=True)
    columns = [(ticker, 'Open'), (ticker, 'High'), (ticker, "Low"), (ticker, "Close"), (ticker, "Adj Close"),
               (ticker, "Volume")]
    newDF.columns = pd.MultiIndex.from_tuples(columns)
    newDF = newDF.sort_index(axis=1)
    return newDF


def get_current_tickers_info(bucket):
    """(string) => pd DataFrame
    Accesses the TickersInfo file on S3,
    returns a DataFrame with the data contained in the file"""
    s3_client = boto3.client("s3")
    object_key = "TickersInfo.csv"
    csv_obj = s3_client.get_object(Bucket=bucket, Key=object_key)
    body = csv_obj['Body']
    csv_string = body.read().decode('utf-8')
    df = pd.read_csv(StringIO(csv_string), index_col=[0])
    return df


def add_days_since_change(df, col_name):
    """(pd DataFrame, string) => pd DataFrame
    Takes in a dataframe and the name of the column in the dataframe that needs to be analysed.
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


def make_graph(df, ticker, signal_names, height, width):
    """(pd DataFrame, string, list, integer, integer) => string
    Takes in:
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

    graphList1 = []
    graphList2 = []
    for elt in signal_names:
        if elt not in ["Stochastic RSI", "MACD", "ADX"]:
            graphList1.append(elt)
        else:
            graphList2.append(elt)

    print(f"graph list 1 : {graphList1}")
    print(f"graph list 2 : {graphList2}")
    fig1 = go.Figure()

    fig1.add_trace(go.Scatter(name=ticker, x=df["Date"], y=df["Close"]))

    for signalName in graphList1:
        fig1.add_trace(go.Scatter(name=signalName, x=df["Date"], y=df[signalName]))

    fig1.update_layout(title=f"{ticker} prices over the past year", template="seaborn",
                       legend={"orientation": "h", "xanchor": "left"},
                       xaxis={
                           "rangeselector": {
                               "buttons": buttons
                           }}, width=width, height=height,
                       )
    graph1 = fig1.to_html(full_html=False)

    if len(graphList2) == 0:
        graph2 = None

    else:

        fig2 = go.Figure()

        for signalName in graphList2:
            fig2.add_trace(go.Scatter(name=signalName, x=df["Date"], y=df[signalName]))

        fig2.update_layout(title=f"{ticker} - {', '.join(graphList2)} over the past year", template="seaborn",
                           legend={"orientation": "h", "xanchor": "left"},
                           xaxis={
                               "rangeselector": {
                                   "buttons": buttons
                               }}, width=width, height=height,
                           )
        graph2 = fig2.to_html(full_html=False)

    return graph1, graph2


def format_float(number):
    """(float) => string
    Takes a number that needs to be formatted, returns a string formatted as a float with 2 decimal places
    """
    string = '{0:.2f}'.format(number)
    return string


def calculate_price_dif(new_price, old_price):
    """(float/integer, float/integer => float/integer, string
    Takes an old price and a new price, returns the difference as a number
    as well as percentage of the old price"""
    price_dif = new_price - old_price
    perc_dif = format_float(price_dif / old_price * 100)
    return price_dif, perc_dif


def get_price_change(df):
    """(pd DataFrame) => (float, tuple)
    Takes in Pandas DataFrame with stock prices for a specific instrument,
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
    change = (f"{sign}{percDif}%", color)
    return closingPrice, change


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

        print(backTestClean.tail())

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
        print(adj_v)
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
