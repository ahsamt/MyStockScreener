from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from .models import User
from django.db import IntegrityError
from .forms import StockForm
from .utils import read_stock_data_from_S3, get_current_tickers, add_ma, add_psar, add_adx, add_srsi, add_macd, \
    adjust_start,  make_graph, add_days_since_change
from .recommendations import add_final_rec_column
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
import os
import numpy as np
import json
import ta
import json
import urllib.request
import urllib.parse


signalOptions = sorted((
    ("SMAS", "Simple Moving Average (SMA) - short window"),
    ("SMAL", "Simple Moving Average (SMA) - long window"),
    ("EMA", " Exponential Moving Average (EMA)"),
    ("PSAR", "Parabolic Stop And Reverse (Parabolic SAR)"),
    ("ADX", "Average Directional Movement Index (ADX)"),
    ("SRSI", "Stochastic RSI (SRSI)"),
    ("MACD", "Moving Average Convergence Divergence (MACD)"),
))

numMonths = 12
bucket = 'stockscreener-data'

def index(request):
    if request.method == "GET":
        return render(request, "stock_screener/index.html", {"stockForm": StockForm()})

    if request.method == "POST":
        if 'ticker' in request.POST:
            stockForm = StockForm(request.POST)
            print("ticker in the request.post")
            #Get all the form data
            if stockForm.is_valid():
                print("stock form is valid")
                ticker = stockForm.cleaned_data['ticker'].upper()
                ma = stockForm.cleaned_data['ma']
                maS = stockForm.cleaned_data['maS']
                maL = stockForm.cleaned_data['maL']
                maWS = stockForm.cleaned_data['maWS']
                maWL = stockForm.cleaned_data['maWL']

                psar = stockForm.cleaned_data['psar']
                psarAF = stockForm.cleaned_data['psarAF']
                psarMA = stockForm.cleaned_data['psarMA']
                adx = stockForm.cleaned_data['adx']
                adxW = stockForm.cleaned_data['adxW']
                adxL = stockForm.cleaned_data['adxW']

                srsi = stockForm.cleaned_data['srsi']
                srsiW = stockForm.cleaned_data['srsiW']
                srsiSm1 = stockForm.cleaned_data['srsiSm1']
                srsiSm2 = stockForm.cleaned_data['srsiSm2']
                srsiOB = stockForm.cleaned_data['srsiOB']
                srsiOS = stockForm.cleaned_data['srsiOS']

                macd = stockForm.cleaned_data['macd']
                macdF = stockForm.cleaned_data['macdF']
                macdS = stockForm.cleaned_data['macdS']
                macdSm = stockForm.cleaned_data['macdSm']

                tickerList = get_current_tickers(bucket)
                if ticker not in tickerList:
                    message = "This ticker will need to be added to S3 bucket"
                    context = {
                        "message": message,
                        "stockForm": StockForm
                    }
                    return render(request, "stock_screener/index.html", context)

                else:
                    print("reading data and preparing graph")
                    stock = read_stock_data_from_S3(bucket, ticker)
                    endDate = date.today()
                    startDate = endDate + relativedelta(months=-numMonths)
                    #startDateInternal = startDate + relativedelta(months=-3)
                    startDateDatetime = datetime.combine(startDate, datetime.min.time())
                    height = 700
                    width = 800

                    graphSignals = []

                    if not (ma or psar or adx or srsi or macd):
                        stock = stock.reset_index()
                        recommendation = "You have not added any signals to this search. " \
                                         "Please select relevant signals on the search page " \
                                         "to see additional information for the selected stock."
                    if ma:
                        stock, shortName, longName = add_ma(stock, maS, maL, maWS, maWL)
                        graphSignals.append(shortName)
                        graphSignals.append(longName)

                    if psar:
                        stock = add_psar(stock, psarAF, psarMA)
                        graphSignals.append("Parabolic_SAR")

                    if adx:
                        stock = add_adx(stock, adxW, adxL)
                        graphSignals.append("ADX")

                    if srsi:
                        stock = add_srsi(stock, srsiW, srsiSm1, srsiSm2, srsiOB, srsiOS)
                        graphSignals.append("Stochastic_RSI")

                    if macd:
                        stock = add_macd(stock, macdS, macdF, macdSm)
                        graphSignals.append("MACD")

                    stock = add_final_rec_column(stock, [adx, ma, macd, psar, srsi])

                    stock = add_days_since_change(stock, "Final_Rec")
                    stock = adjust_start(stock, startDateDatetime)

                    graph = make_graph(stock, ticker, graphSignals, height, width)

                    rec = stock.loc[stock.index[-1], "Final_Rec"].lower()
                    daysSinceChange = stock.loc[stock.index[-1], "Days_Since_Change"]

                    if rec in ["trending", "rangebound"]:
                        recommendation = f"{ticker} is {rec} at the moment."
                    else:

                        recommendation = f"Analysis based on the signals selected " \
                                     f"suggests that you should {rec}."
                    if daysSinceChange is None:
                        changeInfo = "This trend has not changed in the past year"
                    elif str(daysSinceChange)[-1] == 1:
                        changeInfo = f"{daysSinceChange} day since trend change"
                    else:
                        changeInfo = f"{daysSinceChange} day since trend change"

                    print(graphSignals)
                    context = {
                            "ticker": ticker,
                            "graph": graph,
                            "recommendation": recommendation,
                            "changeInfo": changeInfo,
                            "stockForm": stockForm,
                    }
                    # data1, data2 = prep_graph_data(stock)
                    # stockFull = sp500[stock]
                    # closing_price, change = get_change_info(data1, stock)
                    # graph1 = make_graph_1(data1, stock, 470, 630)
                    # graph2 = make_graph_2(data2, stock, 470, 630)
                    # watchlisted = False
                    # stockID = None

                    # if request.user.is_authenticated:
                    #     searchObj = SavedSearch.objects.filter(user=request.user, stock=ticker)
                    #     if len(searchObj):
                    #         watchlisted = True
                    #         stockID = searchObj[0].id

                    # context = {
                    #     "stockForm": stockForm,
                    #     "stock": stock,
                    #     "stockFull": stockFull,
                    #     "stockID": stockID,
                    #     "closing_price": closing_price,
                    #     "change": change,
                    #     "watchlisted": watchlisted,
                    #     "graph1": graph1,
                    #     "graph2": graph2
                    # }

                    return render(request, "stock_screener/index.html", context)
        else:
            print("ticker not in request.post")

def login_view(request):
    if request.method == "POST":
        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication is successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "stock_screener/login.html", {"message": "Invalid username and/or password"})
    else:
        return render(request, "stock_screener/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]

        # Make sure password matches password confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "stock_screener/register.html", {
                "message": "Please make sure the passwords match"
            })

        # Attempt to create a new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "stock_screener/register.html", {
                "message": "Sorry, this username is not available"
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "stock_screener/register.html")
