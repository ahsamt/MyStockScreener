import ta
from .utils import add_days_since_change
import numpy as np


def add_ma(df, ma_short, ma_long, window_short, window_long):
    """(pd DataFrame, string, string, integer, integer) => pd DataFrame, string, string
    Takes in :
        - stock data,
        - types of Moving Average signal (SMA/EMA) for a short and long window
        - sizes of the window for short and long window
    Returns a DataFrame with the Moving Average calculations and recommendations added,
    name of the column representing short MA window, name of the column representing long MA window
    """
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
    """(pd DataFrame, float, float) => pd DataFrame
    Takes in :
        - stock data,
        - Acceleration Factor,
        - Maximum Acceleration
    Returns a DataFrame with the Parabolic SAR calculations and recommendations added"""
    if 'Date' not in df.columns:
        df = df.reset_index()
    df["Parabolic SAR"] = ta.trend.PSARIndicator(df["High"], df["Low"], df["Close"], psar_af, psar_ma).psar()
    mask = df["Parabolic SAR"] > df["Close"]
    df["Parabolic SAR Rec"] = "Buy"
    df.loc[mask, "Parabolic SAR Rec"] = "Sell"
    return df


def add_adx(df, window_size, limit):
    """(pd DataFrame, integer, integer) => pd DataFrame
    Takes in :
        - stock data,
        - window size,
        - limit value above which an instrument is considered to be trending
    Returns a DataFrame with the Average Directional Index calculations and recommendations added"""
    if 'Date' not in df.columns:
        df = df.reset_index()
    df["ADX"] = ta.trend.ADXIndicator(df["High"], df["Low"], df["Close"], window=window_size).adx()
    mask = df["ADX"] > limit
    df["ADX Rec"] = False
    df.loc[mask, "ADX Rec"] = True
    return df


def add_srsi(df, window_size, smooth1, smooth2, overbought_limit, oversold_limit):
    """(pd DataFrame, integer, integer, integer, float, float) => pd DataFrame
    Takes in :
        - stock data,
        - window size,
        - smooth 1 value,
        - smooth 2 value,
        - overbought limit,
        - oversold limit
    Returns a DataFrame with the Stochastic RSI calculations and recommendations added"""
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
    """(pd DataFrame, integer, integer, integer) => pd DataFrame
        Takes in :
            - stock data,
            - window size - slow,
            - swindow size - fast,
            - smoothing period
        Returns a DataFrame with the Moving Average Convergence Divergence
         calculations and recommendations added"""
    if 'Date' not in df.columns:
        df = df.reset_index()
    df["MACD"] = ta.trend.MACD(df["Close"], window_slow=window_slow, window_fast=window_fast,
                               window_sign=smoothing_period).macd()
    mask = df["MACD"] >= 0
    df["MACD Rec"] = "Sell"
    df.loc[mask, "MACD Rec"] = "Buy"
    return df


def add_final_rec_column(df, active_signals):
    recDict = {'ma': 'MA Rec',
               'adx': 'ADX Rec',
               'macd': 'MACD Rec',
               'psar': 'Parabolic SAR Rec',
               'srsi': 'Stochastic RSI Rec'}

    print(active_signals)

    signal_num = len(active_signals)

    if signal_num == 1:
        if 'adx' in active_signals:
            df["Final Rec"] = np.where(df["ADX Rec"] == True, "Trending", "Rangebound")
        else:
            for signal in active_signals:
                df["Final Rec"] = df[recDict[signal]]

    elif signal_num == 2:
        if 'adx' in active_signals:
            signals_other_than_adx = active_signals.copy()
            signals_other_than_adx.remove('adx')
            mask = df["ADX Rec"] == True
            df["Final Rec"] = np.where(mask, df[recDict[signals_other_than_adx[0]]], "Wait")

        else:
            mask = df[recDict[active_signals[0]]] == df[recDict[active_signals[1]]]
            df["Final Rec"] = np.where(mask, df[recDict[active_signals[0]]], "Wait")

    elif signal_num == 3:
        if 'adx' in active_signals:
            mask1 = df["ADX Rec"] == True
            signals_other_than_adx = active_signals.copy()
            signals_other_than_adx.remove('adx')
            mask2 = df[recDict[signals_other_than_adx[0]]] == df[recDict[signals_other_than_adx[1]]]
            mask = mask1 & mask2
            df["Final Rec"] = np.where(mask, df[recDict[signals_other_than_adx[0]]], "Wait")

        else:
            mask = df[recDict[active_signals[0]]] == df[recDict[active_signals[1]]] == df[recDict[active_signals[2]]]
            df["Final Rec"] = np.where(mask, df[recDict[active_signals[0]]], "Wait")


    elif signal_num == 4:
        if 'adx' in active_signals:
            mask1 = df["ADX Rec"] == True
            signals_other_than_adx = active_signals.copy()
            signals_other_than_adx.remove('adx')
            mask2 = (df[recDict[signals_other_than_adx[0]]] == df[recDict[signals_other_than_adx[1]]]) & (
                    df[recDict[signals_other_than_adx[1]]] == df[recDict[signals_other_than_adx[2]]])
            mask = mask1 & mask2
            df["Final Rec"] = np.where(mask, df[recDict[signals_other_than_adx[0]]], "Wait")

        else:
            mask = (df[recDict[active_signals[0]]] == df[recDict[active_signals[1]]]) & (
                    df[recDict[active_signals[1]]] == df[recDict[active_signals[2]]]) & (
                           df[recDict[active_signals[2]]] == df[recDict[active_signals[3]]])
            df["Final Rec"] = np.where(mask, df[recDict[active_signals[0]]], "Wait")

    elif signal_num == 5:
        if 'adx' in active_signals:
            mask1 = df["ADX Rec"] == True
            signals_other_than_adx = active_signals.copy()
            signals_other_than_adx.remove('adx')
            mask2 = (df[recDict[signals_other_than_adx[0]]] == df[recDict[signals_other_than_adx[1]]]) & (
                    df[recDict[signals_other_than_adx[1]]] == df[recDict[signals_other_than_adx[2]]]) & (
                            df[recDict[signals_other_than_adx[2]]] == df[recDict[signals_other_than_adx[3]]])
            mask = mask1 & mask2
            df["Final Rec"] = np.where(mask, df[recDict[signals_other_than_adx[0]]], "Wait")

        else:
            mask = (df[recDict[active_signals[0]]] == df[recDict[active_signals[1]]]) & (
                    df[recDict[active_signals[1]]] == df[recDict[active_signals[2]]]) & (
                           df[recDict[active_signals[2]]] == df[recDict[active_signals[3]]]) & (
                           df[recDict[active_signals[3]]] == df[recDict[active_signals[4]]])
            df["Final Rec"] = np.where(mask, df[recDict[active_signals[0]]], "Wait")
    return df

def make_calculations(stock_df, signal_dict):
    signals_available = ['adx', 'ma', 'macd', 'psar', 'srsi']
    selectedSignals = []

    if signal_dict['ma']:
        stock_df, shortName, longName = add_ma(stock_df, signal_dict['maS'], signal_dict['maL'],
                                               signal_dict['maWS'], signal_dict['maWL'])
        selectedSignals.append(shortName)
        selectedSignals.append(longName)

    if signal_dict['psar']:
        stock_df = add_psar(stock_df, signal_dict['psarAF'], signal_dict['psarMA'])
        selectedSignals.append("Parabolic SAR")

    if signal_dict['adx']:
        stock_df = add_adx(stock_df, signal_dict['adxW'], signal_dict['adxL'])
        selectedSignals.append("ADX")

    if signal_dict['srsi']:
        stock_df = add_srsi(stock_df, signal_dict['srsiW'], signal_dict['srsiSm1'], signal_dict['srsiSm2'],
                            signal_dict['srsiOB'], signal_dict['srsiOS'])
        selectedSignals.append("Stochastic RSI")

    if signal_dict['macd']:
        stock_df = add_macd(stock_df, signal_dict['macdS'], signal_dict['macdF'], signal_dict['macdSm'])
        selectedSignals.append("MACD")

    # Create a list of the signals selected
    active_signals = [k for k in signals_available if signal_dict[k]]

    stock_df = add_final_rec_column(stock_df, active_signals)

    stock_df = add_days_since_change(stock_df, "Final Rec")

    return stock_df, selectedSignals
