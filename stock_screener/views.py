from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from .models import User, SavedSearch, SignalConstructor
from django.db import IntegrityError
from .forms import StockForm, BacktestForm
from .utils import read_csv_from_S3, adjust_start, make_graph, get_price_change, get_current_tickers_info, \
    upload_csv_to_S3, stock_tidy_up, prepare_ticker_info_update, get_company_name_from_yf, get_previous_sma, \
    calculate_price_dif, format_float, backtest_signal, check_for_sma_column, add_sma_col
from .calculations import make_calculations
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
import yfinance as yf
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

numMonths = 12
bucket = 'stockscreener-data'


def index(request):
    if request.method == "GET":
        return render(request, "stock_screener/index.html", {"stockForm": StockForm()})

    if request.method == "POST":
        if 'ticker' in request.POST:
            stockForm = StockForm(request.POST)

            # Get all the form data
            if stockForm.is_valid():
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
                adxL = stockForm.cleaned_data['adxL']

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


                if (adx and not (ma or psar or srsi or macd)):
                    context = {
                        "message": "Please add another signal - ADX alone does not provide buy/sell recommendations",
                        "stockForm": stockForm
                    }
                    return render(request, "stock_screener/index.html", context)

                # Calculating the start date according to client requirements
                endDate = date.today()
                startDate = endDate + relativedelta(months=-numMonths)
                startDateDatetime = datetime.combine(startDate, datetime.min.time())

                signalResults = []

                # setting height and width for the graph
                height = 575
                width = 840

                # getting stocks data from S3
                existingStocks = read_csv_from_S3(bucket, "Stocks")
                tickerList = set(existingStocks.columns.get_level_values(0).tolist())
                tickerInfo = get_current_tickers_info(bucket)

                if ticker not in tickerList:
                    # download data from Yahoo Finance if not available from S3
                    # making sure it covers the same range of dates
                    firstDate = existingStocks.index.min().date() + relativedelta(days=1)
                    lastDate = existingStocks.index.max().date() + relativedelta(days=1)
                    stock = yf.download(ticker, start=firstDate, end=lastDate)

                    if stock.empty:
                        message = f"Details for ticker {ticker} cannot be found"
                        context = {
                            "message": message,
                            "stockForm": StockForm
                        }
                        return render(request, "stock_screener/index.html", context)
                    else:
                        print("Data downloaded in full")

                        # get full company name for the ticker and save info on S3
                        tickerName = get_company_name_from_yf(ticker)
                        tickerInfo = prepare_ticker_info_update(tickerInfo, ticker, tickerName)
                        upload_csv_to_S3(bucket, tickerInfo, "TickersInfo")

                        # prepare stock data for concatenation with the table on S3
                        updatedStock = stock_tidy_up(stock, ticker)

                        # update stock data table and upload back on S3
                        updatedStocks = pd.concat([existingStocks, updatedStock], axis=1)
                        upload_csv_to_S3(bucket, updatedStocks, "Stocks")

                        tickerList = set(updatedStocks.columns.get_level_values(0).tolist())

                else:
                    print("reading data and preparing graph")
                    stock = existingStocks[ticker].copy()

                # getting full company name for the selected ticker
                tickerName = tickerInfo.loc[ticker]["Name"]

                # removing NaN values from the stock data
                stock.dropna(how="all", inplace=True)

                signals = [ma, maS, maL, maWS, maWL, psar, psarAF, psarMA, adx, adxW, adxL, srsi, srsiW, srsiSm1,
                           srsiSm2, srsiOB, srsiOS, macd, macdS, macdF, macdSm]

                # if no signals are selected:
                if not (ma or psar or adx or srsi or macd):
                    signalSelected = False
                    selectedSignals = []
                    stock = stock.reset_index()

                    # getting info for the result table
                    rec = "No signals selected"
                    daysSinceChange = "n/a"



                # if any of the signals are selected:
                else:
                    signalSelected = True

                    # adding columns with calculations for the selected signals
                    stock, selectedSignals = make_calculations(stock, signals)

                    # getting info for the result table
                    rec = stock.loc[stock.index[-1], "Final Rec"]
                    daysSinceChange = stock.loc[stock.index[-1], "Days_Since_Change"]

                # getting last closing price for the ticker + price change information to display in the results window
                closingPrice, priceChange = get_price_change(stock)

                # Check if an SMA column has already been added, and add one if it has not been
                smaCol = check_for_sma_column(stock)
                if not smaCol:
                    stock, smaCol = add_sma_col(stock)

                latestDate = stock["Date"].max()
                smaPeriods = [7, 30, 90]
                smaChanges = []

                # getting the SMA value changes for the ticker going back the number of days indicated in the smaPeriods list
                for noDays in smaPeriods:
                    smaValue = get_previous_sma(stock, smaCol, latestDate, noDays)
                    smaChanges.append(calculate_price_dif(closingPrice, smaValue)[1] + "%")

                # adjusting the start date according to client requirements and preparing the graph
                stock = adjust_start(stock, startDateDatetime)
                graph = make_graph(stock, ticker, selectedSignals, height, width)

                if signalSelected:
                    # preparing backtesting information to be shown on search page
                    backtestResult, backtestDataFull = backtest_signal(stock)

                    if backtestDataFull is not None:
                        backtestData = backtestDataFull.loc[:, ["Close", "Final Rec", "Profit/Loss"]]
                        backtestData.reset_index(inplace=True)
                        # backtestData.rename_axis(None, inplace=True)
                        backtestData.columns = ["Date", "Closing Price", "Recommendation", "Profit/Loss"]

                        htmlBacktestTable = backtestData.to_html(col_space=30, bold_rows=True, classes="table",
                                                                 justify="left", index=False)
                    else:
                        htmlBacktestTable = None
                else:
                    backtestResult, htmlBacktestTable = None, None

                # Preparing the results table to be shown on search page
                for signal in selectedSignals:
                    signalResults.append(format_float(stock.loc[stock.index.max()][signal]))
                data = [rec, daysSinceChange] + smaChanges + signalResults
                resultTable = pd.DataFrame([data],
                                           columns=['Analysis Outcome',
                                                    'Days Since Trend Change',
                                                    '1 Week Change',
                                                    '1 Month Change',
                                                    '3 Months Change'] + selectedSignals)
                resultTable.set_index('Analysis Outcome', inplace=True)
                resultTable = resultTable.transpose()
                htmlResultTable = resultTable.to_html(col_space=30, bold_rows=True, classes="table", justify="left")

                watchlisted = False
                tickerID = None
                constructorAdded = False
                savedConstructor = None
                newSignal = None

                if request.user.is_authenticated:
                    # checking if the ticker user is searching for is in their watchlist
                    searchObj = SavedSearch.objects.filter(user=request.user, ticker=ticker)
                    if len(searchObj):
                        watchlisted = True
                        tickerID = searchObj[0].id

                    # checking if the user has previously saved any signal for their watchlist
                    constructorObj = SignalConstructor.objects.filter(user=request.user)
                    if len(constructorObj):
                        savedConstructor = constructorObj[0]

                        # checking if the signal user has previously saved
                        # matches the signal being used for the current search
                        if (savedConstructor.ma == ma
                                and savedConstructor.maS == maS
                                and savedConstructor.maL == maL
                                and savedConstructor.maWS == maWS
                                and savedConstructor.maWL == maWL
                                and savedConstructor.psar == psar
                                and savedConstructor.psarAF == psarAF
                                and savedConstructor.psarMA == psarMA
                                and savedConstructor.adx == adx
                                and savedConstructor.adxW == adxW
                                and savedConstructor.adxL == adxL
                                and savedConstructor.srsi == srsi
                                and savedConstructor.srsiW == srsiW
                                and savedConstructor.srsiSm1 == srsiSm1
                                and savedConstructor.srsiSm2 == srsiSm2
                                and savedConstructor.srsiOB == srsiOB
                                and savedConstructor.srsiOS == srsiOS
                                and savedConstructor.macd == macd
                                and savedConstructor.macdF == macdF
                                and savedConstructor.macdS == macdS
                                and savedConstructor.macdSm == macdSm):
                            constructorAdded = True

                    newSignal = {"ma": ma, "maS": maS, "maL": maL, "maWS": maWS, "maWL": maWL, "psar": psar,
                                 "psarAF": psarAF, "psarMA": psarMA, "adx": adx, "adxW": adxW, "adxL": adxL,
                                 "srsi": srsi, "srsiW": srsiW, "srsiSm1": srsiSm1, "srsiSm2": srsiSm2,
                                 "srsiOB": srsiOB, "srsiOS": srsiOS, "macd": macd, "macdF": macdF,
                                 "macdS": macdS, "macdSm": macdSm}

                print(stock.tail(15))
                context = {
                    "ticker": ticker,
                    "tickerName": tickerName,
                    "graph": graph,
                    "rec": rec,
                    "closingPrice": format_float(closingPrice),
                    "priceChange": priceChange,
                    "htmlResultTable": htmlResultTable,
                    "stockForm": stockForm,
                    "watchlisted": watchlisted,
                    "tickerID": tickerID,
                    "savedConstructor": savedConstructor,
                    "constructorAdded": constructorAdded,
                    "newSignal": newSignal,
                    "backtestResult": backtestResult,
                    "htmlBacktestTable": htmlBacktestTable,
                    "signalSelected": signalSelected,
                }

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


@csrf_exempt
@login_required
def saved_searches(request):
    # Creating a new saved search must be via POST
    if request.method != "POST":
        return JsonResponse({"error": "POST request required."}, status=400)

    # Check received data emails
    data = json.loads(request.body)

    ticker = data.get("ticker")
    if ticker == [""]:
        return JsonResponse({
            "error": "Ticker name is required."
        }, status=400)
    ticker_full = data.get("ticker_full")

    # Create a saved search for the logged in user
    savedSearch = SavedSearch(
        user=request.user,
        ticker=ticker,
        ticker_full=ticker_full,
    )
    savedSearch.save()
    search_id = savedSearch.id
    return JsonResponse({"message": "Search saved successfully", "id": search_id}, status=201)


@csrf_exempt
@login_required
def saved_search(request, search_id):
    # Query for requested search
    try:
        search = SavedSearch.objects.get(user=request.user, pk=search_id)
    except SavedSearch.DoesNotExist:
        return JsonResponse({"error": "No such search has been saved for this user."}, status=404)

    # Return saved search contents
    if request.method == "GET":
        return JsonResponse(search.serialize())

    # Update notes for the saved search
    elif request.method == "PUT":
        data = json.loads(request.body)
        if data.get("notes") is not None:
            search.notes = data["notes"]
        search.save()
        return HttpResponse(status=204)

    elif request.method == "DELETE":
        search.delete()
        return HttpResponse(status=204)

    # Search must be via GET, PUT or DELETE
    else:
        return JsonResponse({
            "error": "GET, PUT or DELETE request required."
        }, status=400)


@csrf_exempt
@login_required
def saved_signals(request):
    # Creating a new saved signal must be via POST
    if request.method != "POST":
        return JsonResponse({"error": "POST request required."}, status=400)

    # Check received data emails
    data = json.loads(request.body)

    ma = data.get("ma")
    print(ma)
    if ma == "":
        return JsonResponse({
            "error": "True or False is required."
        }, status=400)
    maS = data.get("maS")
    if not maS:
        return JsonResponse({
            "error": "String is required."
        }, status=400)
    maL = data.get("maL")
    maWS = data.get("maWS")
    maWL = data.get("maWL")
    psar = data.get("psar")
    psarAF = data.get("psarAF")
    psarMA = data.get("psarMA")
    adx = data.get("adx")
    adxW = data.get("adxW")
    adxL = data.get("adxL")

    srsi = data.get("srsi")
    srsiW = data.get("srsiW")
    srsiSm1 = data.get("srsiSm1")
    srsiSm2 = data.get("srsiSm2")
    srsiOB = data.get("srsiOB")
    srsiOS = data.get("srsiOS")

    macd = data.get("macd")
    macdF = data.get("macdF")
    macdS = data.get("macdS")
    macdSm = data.get("macdSm")
    previousSignal = data.get("previousSignal")

    # Create a saved search for the logged in user
    try:
        oldSignal = SignalConstructor.objects.get(user=request.user)
        oldSignal.delete()
    except SignalConstructor.DoesNotExist:
        print("nothing to delete")
    print("creating constructor")
    print("values are: ", previousSignal)
    newSignal = SignalConstructor(
        user=request.user,
        ma=ma,
        maS=maS,
        maL=maL,
        maWS=maWS,
        maWL=maWL,
        psar=psar,
        psarAF=psarAF,
        psarMA=psarMA,
        adx=adx,
        adxW=adxW,
        adxL=adxL,

        srsi=srsi,
        srsiW=srsiW,
        srsiSm1=srsiSm1,
        srsiSm2=srsiSm2,
        srsiOB=srsiOB,
        srsiOS=srsiOS,

        macd=macd,
        macdF=macdF,
        macdS=macdS,
        macdSm=macdSm,
    )
    newSignal.save()
    signal_id = newSignal.id

    return JsonResponse({"message": "Signal saved successfully", "id": signal_id}, status=201)


def watchlist(request):
    endDate = date.today()
    startDate = endDate + relativedelta(months=-numMonths)
    startDateInternal = startDate + relativedelta(months=-6)
    startDateDatetime = datetime.combine(startDate, datetime.min.time())
    if request.method == "GET":

        if request.user.is_authenticated:

            watched_tickers = []
            graphs = []
            watchlist = SavedSearch.objects.filter(user=request.user)
            if len(watchlist) == 0:
                return render(request, "stock_screener/watchlist.html", {"empty_message": "You do not have any tickers added to your watchlist"})

            watchlist = sorted(watchlist, key=lambda p: p.date, reverse=True)
            allStocks = read_csv_from_S3(bucket, "Stocks")

            try:
                signal = SignalConstructor.objects.get(user=request.user)

            except SignalConstructor.DoesNotExist:
                signal = None

            if signal:
                signals = [signal.ma,
                           signal.maS,
                           signal.maL,
                           signal.maWS,
                           signal.maWL,
                           signal.psar,
                           signal.psarAF,
                           signal.psarMA,
                           signal.adx,
                           signal.adxW,
                           signal.adxL,
                           signal.srsi,
                           signal.srsiW,
                           signal.srsiSm1,
                           signal.srsiSm2,
                           signal.srsiOB,
                           signal.srsiOS,
                           signal.macd,
                           signal.macdS,
                           signal.macdF,
                           signal.macdSm]

            signalData = []
            signalHeaders = []
            if signal.ma:
                signalData += [signal.ma,
                           signal.maS,
                           signal.maL,
                           signal.maWS,
                           signal.maWL]
                signalHeaders += ["Moving Average", "Moving Average - Short", "Moving Average - Long", "Moving Average Term - short", "Moving Average Term - Long"]

            if signal.psar:
                signalData += [signal.psar,
                           signal.psarAF,
                           signal.psarMA]
                signalHeaders += ["Parabolic SAR", "Parabolic SAR - Acceleration Factor (AF)", "Parabolic SAR - Maximum Acceleration (MA)"]

            if signal.adx:
                signalData += [signal.adx,
                           signal.adxW,
                           signal.adxL]
                signalHeaders += ["ADX", "ADX Term", "ADX Limit"]

            if signal.srsi:
                signalData +=  [signal.srsi,
                           signal.srsiW,
                           signal.srsiSm1,
                           signal.srsiSm2,
                           signal.srsiOB,
                           signal.srsiOS]
                signalHeaders += ["Stochastic RSI", "Stochastic RSI - Term", "Stochastic RSI - Smooth 1",
                       "Stochastic RSI - Smooth 2", "Stochastic RSI - Overbought Limit", "Stochastic RSI - Oversold Limit"]

            if signal.macd:
                signalData += [signal.macd,
                           signal.macdS,
                           signal.macdF,
                           signal.macdSm]
                signalHeaders += ["MACD", "MACD Slow", "MACD Fast", "MACD Smoothing Period"]

            signalTable = pd.DataFrame([signalData], columns=signalHeaders).transpose().reset_index()

            signalTable = signalTable.to_html(col_space=[400, 100],  classes=["table", "signal_table"],
                                              bold_rows=False, justify="left", header=False, index=False)
            # can i pass it to html as an object instead?
            for item in watchlist:
                ticker = item.ticker
                tickerId = item.id
                watchlist_item = {}
                watchlist_item["ticker"] = ticker
                watchlist_item["tickerFull"] = item.ticker_full
                watchlist_item["notes"] = item.notes
                watchlist_item["tickerID"] = item.id


                data = allStocks[ticker].copy()
                data.dropna(how="all", inplace=True)
                if signal:

                    data, selectedSignals = make_calculations(data, signals)
                    watchlist_item["rec"] = data.loc[data.index[-1], "Final Rec"]
                    watchlist_item["daysSinceChange"] = data.loc[data.index[-1], "Days_Since_Change"]
                else:
                    data = data.reset_index()
                    watchlist_item["rec"] = "No signals selected"
                    watchlist_item["daysSinceChange"] = "n/a"

                closingPrice, priceChange = get_price_change(data)

                # Check if an SMA column has already been added, and add one if it has not been
                smaCol = check_for_sma_column(data)
                if not smaCol:
                    data, smaCol = add_sma_col(data)

                latestDate = data["Date"].max()
                smaPeriods = [7, 30, 90]
                smaChanges = []

                # getting the SMA value changes for the ticker
                # going back the number of days indicated in the smaPeriods list
                for noDays in smaPeriods:
                    smaValue = get_previous_sma(data, smaCol, latestDate, noDays)
                    smaChanges.append(calculate_price_dif(closingPrice, smaValue)[1] + "%")

                closingPrice = format_float(closingPrice)
                data = adjust_start(data, startDateDatetime)
                graph = make_graph(data, ticker, selectedSignals, 600, 800)
                watchlist_item["graph"] = graph

                signalResults = []
                print(selectedSignals)
                for signal in selectedSignals:
                    signalResults.append(format_float(data.loc[data.index.max()][signal]))

                tableEntries = \
                    [f"<span class='watchlist-ticker'>{ticker}</span>",
                     watchlist_item["rec"],
                     watchlist_item["daysSinceChange"],
                     closingPrice] + smaChanges \
                    + signalResults + [f"<button class = 'graph-button' data-ticker={ticker}>See graph</button>"] \
                    + [f"<button class = 'remove-ticker-button' data-ticker_id={tickerId}>Remove</button>"]
                # ['''<a href="{% url 'graph' %}" target="blank"> Graph </a>''']

                watchlist_item["resultTable"] = pd.DataFrame([tableEntries],
                                                             columns=['Ticker',
                                                                      'Analysis Outcome',
                                                                      'Days Since Trend Change',
                                                                      'Closing Price',
                                                                      '1 Week Change',
                                                                      '1 Month Change',
                                                                      '3 Months Change'] + selectedSignals + ["Graph"] +
                                                                     ["Remove From Watchlist?"])

                # resultTable.set_index('Analysis Outcome', inplace=True)
                watched_tickers.append(watchlist_item)
            jointTable = pd.DataFrame(columns=['Ticker',
                                               'Analysis Outcome',
                                               'Days Since Trend Change',
                                               'Closing Price',
                                               '1 Week Change',
                                               '1 Month Change',
                                               '3 Months Change'] + selectedSignals + ["Graph"] +
                                              ["Remove From Watchlist?"])
            for elt in watched_tickers:
                jointTable = pd.concat([jointTable, elt["resultTable"]], axis=0)

            jointTable.set_index("Ticker", inplace=True)
            jointTable.sort_values(by=['Days Since Trend Change', 'Ticker'], inplace=True)
            jointTable.rename_axis(None, inplace=True)

            htmlResultTable = jointTable.to_html(col_space=30, bold_rows=True, classes=["table","result_table"], justify="left",
                                                 escape=False)

        return render(request, "stock_screener/watchlist.html",
                      {'watched_tickers': watched_tickers, "htmlResultTable": htmlResultTable, "signalTable": signalTable})


def backtester(request):
    if request.method == "GET":
        user = request.user
        # watchedTickersObjs = SavedSearch.objects.filter(user=request.user)
        # watchedTickersObjs = sorted(watchedTickersObjs, key=lambda p: p.ticker)
        # watchedTickersNames = [t.ticker for t in watchedTickersObjs]

        return render(request, "stock_screener/backtester.html", {"stockForm": BacktestForm(user)})

    if request.method == "POST":
        print(request.POST)

        if 'tickers' in request.POST:
            backtestForm = BacktestForm(request.user, request.POST)

            # Get all the form data
            if backtestForm.is_valid():

                ma = backtestForm.cleaned_data['ma']
                maS = backtestForm.cleaned_data['maS']
                maL = backtestForm.cleaned_data['maL']
                maWS = backtestForm.cleaned_data['maWS']
                maWL = backtestForm.cleaned_data['maWL']

                psar = backtestForm.cleaned_data['psar']
                psarAF = backtestForm.cleaned_data['psarAF']
                psarMA = backtestForm.cleaned_data['psarMA']
                adx = backtestForm.cleaned_data['adx']
                adxW = backtestForm.cleaned_data['adxW']
                adxL = backtestForm.cleaned_data['adxL']

                srsi = backtestForm.cleaned_data['srsi']
                srsiW = backtestForm.cleaned_data['srsiW']
                srsiSm1 = backtestForm.cleaned_data['srsiSm1']
                srsiSm2 = backtestForm.cleaned_data['srsiSm2']
                srsiOB = backtestForm.cleaned_data['srsiOB']
                srsiOS = backtestForm.cleaned_data['srsiOS']

                macd = backtestForm.cleaned_data['macd']
                macdF = backtestForm.cleaned_data['macdF']
                macdS = backtestForm.cleaned_data['macdS']
                macdSm = backtestForm.cleaned_data['macdSm']

                days_to_buy = backtestForm.cleaned_data["days_to_buy"]
                days_to_sell = backtestForm.cleaned_data["days_to_sell"]
                buy_price_adjustment = backtestForm.cleaned_data["buy_price_adjustment"]
                sell_price_adjustment = backtestForm.cleaned_data["sell_price_adjustment"]

                tickers = backtestForm.cleaned_data['tickers']
                print("tickers are" + str(tickers))
                if "ALL" in tickers:
                    tickers = sorted([o.ticker for o in SavedSearch.objects.filter(user=request.user)])

                # Calculating the start date according to client requirements
                endDate = date.today()
                startDate = endDate + relativedelta(years=-5)
                startDateDatetime = datetime.combine(startDate, datetime.min.time())

                signalResults = []

                # getting stocks data from S3
                existingStocks = read_csv_from_S3(bucket, "Stocks")
                tickerList = set(existingStocks.columns.get_level_values(0).tolist())
                tickerInfo = get_current_tickers_info(bucket)

                signals = [ma, maS, maL, maWS, maWL, psar, psarAF, psarMA, adx, adxW, adxL, srsi, srsiW, srsiSm1,
                           srsiSm2, srsiOB, srsiOS, macd, macdS, macdF, macdSm]
                if not (ma or psar or adx or srsi or macd):
                    context = {
                        "message": "Please select the signals to back test",
                        "stockForm": BacktestForm(request.user)
                    }
                    return render(request, "stock_screener/backtester.html", context)

                elif (adx and not (ma or psar or srsi or macd)):
                    context = {
                        "message": "Please add another signal - ADX alone does not provide buy/sell recommendations",
                        "stockForm": BacktestForm(request.user)
                    }
                    return render(request, "stock_screener/backtester.html", context)

                allResults = {}
                allTables = {}

                for ticker in tickers:
                    stock = existingStocks[ticker].copy()

                    # getting full company name for the selected ticker
                    tickerName = tickerInfo.loc[ticker]["Name"]

                    # removing NaN values from the stock data
                    stock.dropna(how="all", inplace=True)

                    # adding columns with calculations for the selected signals
                    stock, selectedSignals = make_calculations(stock, signals)

                    stock = adjust_start(stock, startDateDatetime)
                    print(stock.tail(5))

                    # preparing backtesting information for the ticker
                    backtestResult, backtestDataFull = backtest_signal(stock,
                                                                       format_outcome=False,
                                                                       days_to_buy=days_to_buy,
                                                                       days_to_sell=days_to_sell,
                                                                       buy_price_adjustment=buy_price_adjustment,
                                                                       sell_price_adjustment=sell_price_adjustment)

                    allResults[ticker] = backtestResult

                    if backtestDataFull is not None:
                        backtestData = backtestDataFull.loc[:, ["Close", "Final Rec", "Price After Delay",
                                                                "Adjusted Price After Delay", "Profit/Loss"]]
                        backtestData.reset_index(inplace=True)
                        # backtestData.rename_axis(None, inplace=True)
                        # backtestData["Price After Delay"] = backtestData["Price After Delay"].apply(lambda x: format_float(x))
                        # backtestData["Adjusted Price After Delay"] = backtestData["Adjusted Price After Delay"].apply(lambda x: format_float(x))
                        backtestData.columns = ["Date", "Closing Price", "Recommendation", "Price After Delay",
                                                "Adjusted Price After Delay", "Profit/Loss"]

                        allTables[ticker] = backtestData.to_html(col_space=20, bold_rows=True, classes="table",
                                                                 justify="left", index=False)

                    else:
                        allTables[
                            ticker] = "The signal has not generated a sufficient number of buy/sell recommendations"

                print(allResults)
                backtesterTable = pd.DataFrame.from_dict(allResults, orient="index")
                backtesterTable.reset_index(inplace=True)
                backtesterTable.columns = ["Ticker", "Profit/Loss"]
                # backtesterTable.set_index("Ticker", inplace=True)
                backtesterTable["Profit/Loss"] = backtesterTable["Profit/Loss"].apply(
                    lambda x: (format_float(x) + " %"))

                backtesterTable["Details"] = ""
                for i in range(backtesterTable.index.max() + 1):
                    nextTicker = backtesterTable.loc[i, "Ticker"]
                    backtesterTable.loc[
                        i, "Details"] = f"<button class = 'ind_outcome_button' data-ticker={nextTicker}>See details</button>"

                htmlJointTable = backtesterTable.to_html(col_space=[150, 200, 150], bold_rows=True,
                                                         classes=["table", "backtest_table"],
                                                         escape=False, index=False)

                overallResult = round(sum(allResults.values()) / len(allResults), 2)

                context = {
                    "overallResult": overallResult,
                    "htmlJointTable": htmlJointTable,
                    "allTables": allTables
                }

                return render(request, "stock_screener/backtester.html", context)

# def graph(request):
# return render(request, "stock_screener/graph.html")
