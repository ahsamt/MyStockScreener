import numpy as np
import pandas as pd


def add_final_rec_column(df, signalList):
    signalNum = sum(signalList)
    adx, ma, macd, psar, srsi = signalList
    print(signalNum)
    if signalNum == 1:
        if adx:
            print("ADX only")
            df["Final_Rec"] = np.where(df["ADX_Rec"] == True, "Trending", "Rangebound")

        elif ma:
            print("MA only")
            df["Final_Rec"] = df["MA_Rec"]

        elif macd:
            print("MA only")
            df["Final_Rec"] = df["MACD_Rec"]

        elif psar:
            print("Parabolic_SAR only")
            df["Final_Rec"] = df["Parabolic_SAR_Rec"]

        elif srsi:
            print("Stochastic_RSI only")
            df["Final_Rec"] = df["Stochastic_RSI_Rec"]

    elif signalNum == 2:

        if adx and ma:
            print("ADX and MA")
            mask = df["ADX_Rec"] == True
            df.loc[mask, "Final_Rec"] = df["MA_Rec"]

        elif adx and macd:
            print("ADX and MACD")
            mask = df["ADX_Rec"] == True
            df["Final_Rec"] = np.where(mask, df["MACD_Rec"], "Wait")

        elif adx and psar:

            print("ADX and Parabolic_SAR")
            mask = df["ADX_Rec"] == True
            df["Final_Rec"] = np.where(mask, df["Parabolic_SAR_Rec"], "Wait")

        elif adx and srsi:

            print("ADX and Parabolic_SAR")
            mask = df["ADX_Rec"] == True
            df["Final_Rec"] = np.where(mask, df["Parabolic_SAR_Rec"], "Wait")

        elif ma and macd:
            print("MA and MACD")
            mask = df["MA_Rec"] == df["MACD_Rec"]
            df["Final_Rec"] = np.where(mask, df["MA_Rec"], "Wait")

        elif ma and psar:

            print("MA and Parabolic_SAR")
            mask = df["MA_Rec"] == df["Parabolic_SAR_Rec"]
            df["Final_Rec"] = np.where(mask, df["MA_Rec"], "Wait")

        elif ma and srsi:

            print("MA and Stochastic_RSI")
            mask = df["MA_Rec"] == df["Stochastic_RSI_Rec"]
            df["Final_Rec"] = np.where(mask, df["MA_Rec"], "Wait")

        elif macd and psar:

            print("MACD and Parabolic_SAR")
            mask = df["MACD_Rec"] == df["Parabolic_SAR_Rec"]
            df["Final_Rec"] = np.where(mask, df["MACD_Rec"], "Wait")

        elif macd and srsi:

            print("MACD and Stochastic_RSI")
            mask = df["MACD_Rec"] == df["Stochastic_RSI_Rec"]
            df["Final_Rec"] = np.where(mask, df["MACD_Rec"], "Wait")


        elif psar and srsi:

            print("Parabolic_SAR and Stochastic_RSI")
            mask = df["Parabolic_SAR_Rec"] == df["Stochastic_RSI_Rec"]
            df["Final_Rec"] = np.where(mask, df["Parabolic_SAR_Rec"], "Wait")

    elif signalNum == 3:

        if adx and ma and macd:

            print("ADX and MA and MACD")
            mask = (df["ADX_Rec"] == True) & (df["MA_Rec"] == df["MACD_Rec"])
            df["Final_Rec"] = np.where(mask, df["MA_Rec"], "Wait")

        elif adx and ma and psar:

            print("ADX and MA and Parabolic_SAR")
            mask = (df["ADX_Rec"] == True) & (df["MA_Rec"] == df["Parabolic_SAR_Rec"])
            df["Final_Rec"] = np.where(mask, df["MA_Rec"], "Wait")

        elif adx and ma and srsi:
            print("ADX and MA and Stochastic_RSI")
            mask = (df["ADX_Rec"] == True) & (df["MA_Rec"] == df["Stochastic_RSI_Rec"])
            df["Final_Rec"] = np.where(mask, df["MA_Rec"], "Wait")

        elif adx and macd and psar:

            print("ADX and MACD and Parabolic_SAR")
            mask = (df["ADX_Rec"] == True) & (df["MACD_Rec"] == df["Parabolic_SAR_Rec"])
            df["Final_Rec"] = np.where(mask, df["MACD_Rec"], "Wait")

        elif adx and macd and srsi:
            print("ADX and MACD and Stochastic_RSI")
            mask = (df["ADX_Rec"] == True) & (df["MACD_Rec"] == df["Stochastic_RSI_Rec"])
            df["Final_Rec"] = np.where(mask, df["MACD_Rec"], "Wait")


        elif adx and psar and srsi:

            print("ADX and Parabolic_SAR and Stochastic_RSI")
            mask = (df["ADX_Rec"] == True) & (df["Parabolic_SAR_Rec"] == df["Stochastic_RSI_Rec"])
            df["Final_Rec"] = np.where(mask, df["Parabolic_SAR_Rec"], "Wait")

        elif ma and macd and psar:

            print("MA and MACD and Parabolic_SAR")
            mask = (df["MA_Rec"] == df["MACD_Rec"]) & (df["MACD_Rec"] == df["Parabolic_SAR_Rec"])
            df["Final_Rec"] = np.where(mask, df["MA_Rec"], "Wait")


        elif ma and macd and srsi:

            print("MA and MACD and Stochastic_RSI")
            mask = (df["MA_Rec"] == df["MACD_Rec"]) & (df["MACD_Rec"] == df["Stochastic_RSI_Rec"])
            df["Final_Rec"] = np.where(mask, df["MA_Rec"], "Wait")

        elif ma and psar and srsi:

            print("MA and Parabolic_SAR and Stochastic_RSI")
            mask = (df["MA_Rec"] == df["Parabolic_SAR_Rec"]) & (df["Parabolic_SAR_Rec"] == df["Stochastic_RSI_Rec"])
            df["Final_Rec"] = np.where(mask, df["MA_Rec"], "Wait")

        elif macd and psar and srsi:

            print("MACD and Parabolic_SAR and Stochastic_RSI")
            mask = (df["MACD_Rec"] == df["Parabolic_SAR_Rec"]) & (df["Parabolic_SAR_Rec"] == df["Stochastic_RSI_Rec"])
            df["Final_Rec"] = np.where(mask, df["MACD_Rec"], "Wait")

    elif signalNum == 4:

        if adx and ma and macd and psar:
            print("ADX and MA and MACD and Parabolic_SAR")
            mask = (df["ADX_Rec"] == True) & (df["MA_Rec"] == df["MACD_Rec"]) & (
                        df["MACD_Rec"] == df["Parabolic_SAR_Rec"])
            df["Final_Rec"] = np.where(mask, df["MA_Rec"], "Wait")

        elif adx and ma and macd and srsi:

            print("ADX and MA and MACD and Stochastic_RSI")
            mask = (df["ADX_Rec"] == True) & (df["MA_Rec"] == df["MACD_Rec"]) & (
                        df["MACD_Rec"] == df["Stochastic_RSI_Rec"])
            df["Final_Rec"] = np.where(mask, df["MA_Rec"], "Wait")

        elif adx and ma and psar and srsi:

            print("ADX and MA and Parabolic_SAR and Stochastic_RSI")
            mask = (df["ADX_Rec"] == True) & (df["MA_Rec"] == df["Parabolic_SAR_Rec"]) & (
                        df["Parabolic_SAR_Rec"] == df["Stochastic_RSI_Rec"])
            df["Final_Rec"] = np.where(mask, df["MA_Rec"], "Wait")

        elif adx and macd and psar and srsi:

            print("ADX and MACD and Parabolic_SAR and Stochastic_RSI")
            mask = (df["ADX_Rec"] == True) & (df["MACD_Rec"] == df["Parabolic_SAR_Rec"]) & (
                        df["Parabolic_SAR_Rec"] == df["Stochastic_RSI_Rec"])
            df["Final_Rec"] = np.where(mask, df["MACD_Rec"], "Wait")


        elif ma and macd and psar and srsi:

            print("MA and MACD and Parabolic_SAR and Stochastic_RSI")
            mask = (df["MA_Rec"] == df["MACD_Rec"]) & (df["MACD_Rec"] == df["Parabolic_SAR_Rec"]) & (
                        df["Parabolic_SAR_Rec"] == df["Stochastic_RSI_Rec"])
            df["Final_Rec"] = np.where(mask, df["MA_Rec"], "Wait")

    elif signalNum == 5:

        print("All signals")
        mask = (df["ADX_Rec"] == True) & (df["MA_Rec"] == df["MACD_Rec"]) & (
                    df["MACD_Rec"] == df["Parabolic_SAR_Rec"]) & (df["Parabolic_SAR_Rec"] == df["Stochastic_RSI_Rec"])
        df["Final_Rec"] = np.where(mask, df["MA_Rec"], "Wait")

    print(df.tail())
    return df

