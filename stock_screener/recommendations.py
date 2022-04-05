import numpy as np


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
