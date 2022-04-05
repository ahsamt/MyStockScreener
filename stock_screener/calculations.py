import ta
from .utils import add_ma, add_adx, add_psar, add_srsi, add_macd, add_days_since_change
from .recommendations import add_final_rec_column


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
