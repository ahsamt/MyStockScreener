import numpy as np
import pandas as pd


def add_final_rec_column(df, signalList):
    signalNum = sum(signalList)
    adx, ma, macd, psar, srsi = signalList
    print(signalNum)
    if signalNum == 1:
        if adx:
            print("ADX only")
            df["Final Rec"] = np.where(df["ADX Rec"] == True, "Trending", "Rangebound")

        elif ma:
            print("MA only")
            df["Final Rec"] = df["MA Rec"]

        elif macd:
            print("MA only")
            df["Final Rec"] = df["MACD Rec"]

        elif psar:
            print("Parabolic SAR only")
            df["Final Rec"] = df["Parabolic SAR Rec"]

        elif srsi:
            print("Stochastic RSI only")
            df["Final Rec"] = df["Stochastic RSI Rec"]

    elif signalNum == 2:

        if adx and ma:
            print("ADX and MA")
            mask = df["ADX Rec"] == True
            df.loc[mask, "Final Rec"] = df["MA Rec"]

        elif adx and macd:
            print("ADX and MACD")
            mask = df["ADX Rec"] == True
            df["Final Rec"] = np.where(mask, df["MACD Rec"], "Wait")

        elif adx and psar:

            print("ADX and Parabolic SAR")
            mask = df["ADX Rec"] == True
            df["Final Rec"] = np.where(mask, df["Parabolic SAR Rec"], "Wait")

        elif adx and srsi:

            print("ADX and Stochastic RSI")
            mask = df["ADX Rec"] == True
            df["Final Rec"] = np.where(mask, df["Stochastic RSI Rec"], "Wait")

        elif ma and macd:
            print("MA and MACD")
            mask = df["MA Rec"] == df["MACD Rec"]
            df["Final Rec"] = np.where(mask, df["MA Rec"], "Wait")

        elif ma and psar:

            print("MA and Parabolic SAR")
            mask = df["MA Rec"] == df["Parabolic SAR Rec"]
            df["Final Rec"] = np.where(mask, df["MA Rec"], "Wait")

        elif ma and srsi:

            print("MA and Stochastic RSI")
            mask = df["MA Rec"] == df["Stochastic RSI Rec"]
            df["Final Rec"] = np.where(mask, df["MA Rec"], "Wait")

        elif macd and psar:

            print("MACD and Parabolic SAR")
            mask = df["MACD Rec"] == df["Parabolic SAR Rec"]
            df["Final Rec"] = np.where(mask, df["MACD Rec"], "Wait")

        elif macd and srsi:

            print("MACD and Stochastic RSI")
            mask = df["MACD Rec"] == df["Stochastic RSI Rec"]
            df["Final Rec"] = np.where(mask, df["MACD Rec"], "Wait")


        elif psar and srsi:

            print("Parabolic SAR and Stochastic RSI")
            mask = df["Parabolic SAR Rec"] == df["Stochastic RSI Rec"]
            df["Final Rec"] = np.where(mask, df["Parabolic SAR Rec"], "Wait")

    elif signalNum == 3:

        if adx and ma and macd:

            print("ADX and MA and MACD")
            mask = (df["ADX Rec"] == True) & (df["MA Rec"] == df["MACD Rec"])
            df["Final Rec"] = np.where(mask, df["MA Rec"], "Wait")

        elif adx and ma and psar:

            print("ADX and MA and Parabolic SAR")
            mask = (df["ADX Rec"] == True) & (df["MA Rec"] == df["Parabolic SAR Rec"])
            df["Final Rec"] = np.where(mask, df["MA Rec"], "Wait")

        elif adx and ma and srsi:
            print("ADX and MA and Stochastic RSI")
            mask = (df["ADX Rec"] == True) & (df["MA Rec"] == df["Stochastic RSI Rec"])
            df["Final Rec"] = np.where(mask, df["MA Rec"], "Wait")

        elif adx and macd and psar:

            print("ADX and MACD and Parabolic SAR")
            mask = (df["ADX Rec"] == True) & (df["MACD Rec"] == df["Parabolic SAR Rec"])
            df["Final Rec"] = np.where(mask, df["MACD Rec"], "Wait")

        elif adx and macd and srsi:
            print("ADX and MACD and Stochastic RSI")
            mask = (df["ADX Rec"] == True) & (df["MACD Rec"] == df["Stochastic RSI Rec"])
            df["Final Rec"] = np.where(mask, df["MACD Rec"], "Wait")


        elif adx and psar and srsi:

            print("ADX and Parabolic SAR and Stochastic RSI")
            mask = (df["ADX Rec"] == True) & (df["Parabolic SAR Rec"] == df["Stochastic RSI Rec"])
            df["Final Rec"] = np.where(mask, df["Parabolic SAR Rec"], "Wait")

        elif ma and macd and psar:

            print("MA and MACD and Parabolic SAR")
            mask = (df["MA Rec"] == df["MACD Rec"]) & (df["MACD Rec"] == df["Parabolic SAR Rec"])
            df["Final Rec"] = np.where(mask, df["MA Rec"], "Wait")


        elif ma and macd and srsi:

            print("MA and MACD and Stochastic RSI")
            mask = (df["MA Rec"] == df["MACD Rec"]) & (df["MACD Rec"] == df["Stochastic RSI Rec"])
            df["Final Rec"] = np.where(mask, df["MA Rec"], "Wait")

        elif ma and psar and srsi:

            print("MA and Parabolic SAR and Stochastic RSI")
            mask = (df["MA Rec"] == df["Parabolic SAR Rec"]) & (df["Parabolic SAR Rec"] == df["Stochastic RSI Rec"])
            df["Final Rec"] = np.where(mask, df["MA Rec"], "Wait")

        elif macd and psar and srsi:

            print("MACD and Parabolic SAR and Stochastic RSI")
            mask = (df["MACD Rec"] == df["Parabolic SAR Rec"]) & (df["Parabolic SAR Rec"] == df["Stochastic RSI Rec"])
            df["Final Rec"] = np.where(mask, df["MACD Rec"], "Wait")

    elif signalNum == 4:

        if adx and ma and macd and psar:
            print("ADX and MA and MACD and Parabolic SAR")
            mask = (df["ADX Rec"] == True) & (df["MA Rec"] == df["MACD Rec"]) & (
                        df["MACD Rec"] == df["Parabolic SAR Rec"])
            df["Final Rec"] = np.where(mask, df["MA Rec"], "Wait")

        elif adx and ma and macd and srsi:

            print("ADX and MA and MACD and Stochastic RSI")
            mask = (df["ADX Rec"] == True) & (df["MA Rec"] == df["MACD Rec"]) & (
                        df["MACD Rec"] == df["Stochastic RSI Rec"])
            df["Final Rec"] = np.where(mask, df["MA Rec"], "Wait")

        elif adx and ma and psar and srsi:

            print("ADX and MA and Parabolic SAR and Stochastic RSI")
            mask = (df["ADX Rec"] == True) & (df["MA Rec"] == df["Parabolic SAR Rec"]) & (
                        df["Parabolic SAR Rec"] == df["Stochastic RSI Rec"])
            df["Final Rec"] = np.where(mask, df["MA Rec"], "Wait")

        elif adx and macd and psar and srsi:

            print("ADX and MACD and Parabolic SAR and Stochastic RSI")
            mask = (df["ADX Rec"] == True) & (df["MACD Rec"] == df["Parabolic SAR Rec"]) & (
                        df["Parabolic_SAR_Rec"] == df["Stochastic RSI Rec"])
            df["Final Rec"] = np.where(mask, df["MACD Rec"], "Wait")


        elif ma and macd and psar and srsi:

            print("MA and MACD and Parabolic SAR and Stochastic RSI")
            mask = (df["MA Rec"] == df["MACD Rec"]) & (df["MACD Rec"] == df["Parabolic SAR Rec"]) & (
                        df["Parabolic SAR Rec"] == df["Stochastic RSI Rec"])
            df["Final Rec"] = np.where(mask, df["MA Rec"], "Wait")

    elif signalNum == 5:

        print("All signals")
        mask = (df["ADX Rec"] == True) & (df["MA Rec"] == df["MACD Rec"]) & (
                    df["MACD Rec"] == df["Parabolic SAR Rec"]) & (df["Parabolic SAR Rec"] == df["Stochastic RSI Rec"])
        df["Final Rec"] = np.where(mask, df["MA Rec"], "Wait")

    #print(df.tail())
    return df

