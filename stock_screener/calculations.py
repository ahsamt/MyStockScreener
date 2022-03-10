import ta
from .utils import add_ma, add_adx, add_psar, add_srsi, add_macd, add_days_since_change
from .recommendations import add_final_rec_column


def make_calculations(ticker, ticker_full, stock_df, signals_list):
    selectedSignals = []

    ma, maS, maL, maWS, maWL, psar, psarAF, psarMA, adx, adxW, adxL, srsi, srsiW, srsiSm1, srsiSm2, srsiOB, srsiOS, macd, macdS, macdF, macdSm = signals_list

    if ma:
        stock_df, shortName, longName = add_ma(stock_df, maS, maL, maWS, maWL)
        selectedSignals.append(shortName)
        selectedSignals.append(longName)

    if psar:
        stock_df = add_psar(stock_df, psarAF, psarMA)
        selectedSignals.append("Parabolic SAR")

    if adx:
        stock_df = add_adx(stock_df, adxW, adxL)
        selectedSignals.append("ADX")

    if srsi:
        stock_df = add_srsi(stock_df, srsiW, srsiSm1, srsiSm2, srsiOB, srsiOS)
        selectedSignals.append("Stochastic RSI")

    if macd:
        stock_df = add_macd(stock_df, macdS, macdF, macdSm)
        selectedSignals.append("MACD")

    stock_df = add_final_rec_column(stock_df, [adx, ma, macd, psar, srsi])

    stock_df = add_days_since_change(stock_df, "Final Rec")

    return stock_df, selectedSignals
