from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from .models import User, SavedSearch, SignalConstructor
from django.db import IntegrityError
from .forms import StockForm, BacktestForm
from .utils import read_csv_from_S3, adjust_start, make_graph, get_price_change, get_current_tickers_info, \
    upload_csv_to_S3, stock_tidy_up, prepare_ticker_info_update, get_company_name_from_yf, get_previous_sma, \
    calculate_price_dif, format_float, backtest_signal, prepare_signal_table, calc_average_percentage, check_and_add_sma
from .calculations import make_calculations
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
import yfinance as yf
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

bucket = 'stockscreener-data'
constructorFields = ['ma', 'maS', 'maL', 'maWS', 'maWL', 'psar', 'psarAF', 'psarMA', 'adx', 'adxW', 'adxL', 'srsi',
                     'srsiW', 'srsiSm1', 'srsiSm2', 'srsiOB', 'srsiOS', 'macd', 'macdF', 'macdS', 'macdSm']


def index(request):
    numMonths = 12
    if request.method == "GET":
        return render(request, "stock_screener/index.html", {"stockForm": StockForm()})

    if request.method == "POST":
        if 'ticker' in request.POST:
            stockForm = StockForm(request.POST)
            signalDict = {}
            # Get all the form data
            if stockForm.is_valid():
                ticker = stockForm.cleaned_data['ticker'].upper()

                for k in constructorFields:
                    signalDict[k] = stockForm.cleaned_data[k]

                print(f"Signal dict data :{signalDict}")

                if signalDict['adx'] and not (
                        signalDict['ma'] or signalDict['psar'] or signalDict['srsi'] or signalDict['macd']):
                    context = {
                        "message": "Please add another signal - ADX alone does not provide buy/sell recommendations",
                        "stockForm": stockForm
                    }
                    return render(request, "stock_screener/index.html", context)

                # Calculating the start date according to client requirements
                endDate = date.today()
                startDate = endDate + relativedelta(months=-numMonths)
                startDateInternal = startDate + relativedelta(months=-12)
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

                        # tickerList = set(updatedStocks.columns.get_level_values(0).tolist())

                else:
                    print("reading data and preparing graph")
                    stock = existingStocks[ticker].copy()

                # getting full company name for the selected ticker
                tickerName = tickerInfo.loc[ticker]["Name"]

                # Getting the slice of the data starting from 18 months back
                # (12 required for display + 12 extra for analysis)
                stock = stock.loc[startDateInternal:, :]

                # removing NaN values from the stock data
                stock.dropna(how="all", inplace=True)

                # converting column data types to float
                stock = stock.apply(pd.to_numeric)

                # if no signals are selected:
                if not (signalDict['ma']
                        or signalDict['psar']
                        or signalDict['adx']
                        or signalDict['srsi']
                        or signalDict['macd']):
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
                    stock, selectedSignals = make_calculations(stock, signalDict)

                    # getting info for the result table
                    rec = stock.loc[stock.index[-1], "Final Rec"]
                    daysSinceChange = stock.loc[stock.index[-1], "Days_Since_Change"]

                # getting last closing price for the ticker + price change information to display in the results window
                closingPrice, priceChange = get_price_change(stock)

                # Check if an SMA column has already been added, and add one if it has not been
                stock, smaCol = check_and_add_sma(stock)

                smaPeriods = [7, 30, 90]
                smaChanges = []

                # getting the SMA value changes for the ticker
                # going back the number of days indicated in the smaPeriods list
                for noDays in smaPeriods:
                    smaValue = get_previous_sma(stock, smaCol, noDays)
                    smaChanges.append(calculate_price_dif(closingPrice, smaValue)[1] + "%")

                # adjusting the start date according to client requirements and preparing the graph
                stock = adjust_start(stock, startDateDatetime)
                graph = make_graph(stock, ticker, selectedSignals, height, width)

                if signalSelected:
                    # preparing backtesting information to be shown on search page
                    backtestResult, backtestDataFull = backtest_signal(stock)
                    signalSelected = True

                    if backtestDataFull is not None:
                        backtestData = backtestDataFull.loc[:, ["Close", "Final Rec", "Profit/Loss"]]
                        backtestData.reset_index(inplace=True)
                        backtestData.columns = ["Date", "Closing Price", "Recommendation", "Profit/Loss"]

                        htmlBacktestTable = backtestData.to_html(col_space=30, bold_rows=True, classes="table",
                                                                 justify="left", index=False)
                    else:
                        htmlBacktestTable = None

                else:
                    backtestResult, htmlBacktestTable = None, None
                    signalSelected = False

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
                        if (savedConstructor.ma == signalDict['ma']
                                and savedConstructor.maS == signalDict['maS']
                                and savedConstructor.maL == signalDict['maL']
                                and savedConstructor.maWS == signalDict['maWS']
                                and savedConstructor.maWL == signalDict['maWL']
                                and savedConstructor.psar == signalDict['psar']
                                and savedConstructor.psarAF == signalDict['psarAF']
                                and savedConstructor.psarMA == signalDict['psarMA']
                                and savedConstructor.adx == signalDict['adx']
                                and savedConstructor.adxW == signalDict['adxW']
                                and savedConstructor.adxL == signalDict['adxL']
                                and savedConstructor.srsi == signalDict['srsi']
                                and savedConstructor.srsiW == signalDict['srsiW']
                                and savedConstructor.srsiSm1 == signalDict['srsiSm1']
                                and savedConstructor.srsiSm2 == signalDict['srsiSm2']
                                and savedConstructor.srsiOB == signalDict['srsiOB']
                                and savedConstructor.srsiOS == signalDict['srsiOS']
                                and savedConstructor.macd == signalDict['macd']
                                and savedConstructor.macdF == signalDict['macdF']
                                and savedConstructor.macdS == signalDict['macdS']
                                and savedConstructor.macdSm == signalDict['macdSm']):
                            constructorAdded = True

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
                    "newSignal": signalDict,
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

    # Check received data
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
    # previousSignal = data.get("previousSignal")
    print("Got all the data, about to delete old and save new")
    # Create a saved search for the logged in user
    try:
        oldSignal = SignalConstructor.objects.get(user=request.user)
        oldSignal.delete()
    except SignalConstructor.DoesNotExist:
        print("nothing to delete")
    print("creating constructor")

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


@login_required
def watchlist(request):
    numMonths = 12
    endDate = date.today()
    startDate = endDate + relativedelta(months=-numMonths)
    startDateInternal = startDate + relativedelta(months=-12)
    startDateDatetime = datetime.combine(startDate, datetime.min.time())

    if request.method == "GET":
        watchedTickers = []
        watchlistObjects = SavedSearch.objects.filter(user=request.user)
        if len(watchlistObjects) == 0:
            return render(request, "stock_screener/watchlist.html",
                          {"empty_message": "You do not have any tickers added to your watchlist"})

        # watchlist = sorted(watchlist, key=lambda p: p.date, reverse=True)
        allStocksFull = read_csv_from_S3(bucket, "Stocks")

        # Getting the slice of the data starting from 18 months back (12 required for display + 12 extra for analysis)
        allStocks = allStocksFull.loc[startDateInternal:, :]

        # Check if the user has a signal saved in their profile
        try:
            signal = SignalConstructor.objects.get(user=request.user)

        except SignalConstructor.DoesNotExist:
            return render(request, "stock_screener/watchlist.html",
                          {"empty_message": "Please create and save a signal on the 'Search' page to view "
                                            "recommendations for your watchlist"})

        # Converting the saved signal object to dictionary
        signalDict = vars(signal)

        # prepare a table to display the saved signal to the user
        signalTable = prepare_signal_table(signal)

        # can i pass it to html as an object instead?
        for item in watchlistObjects:
            ticker = item.ticker
            tickerId = item.id
            watchlistItem = {"ticker": ticker, "notes": item.notes, "tickerID": item.id}

            # Creating a separate dataframe for each stock, dropping n/a values and converting data to numeric
            data = allStocks[ticker].copy()
            data.dropna(how="all", inplace=True)
            data = data.apply(pd.to_numeric)

            # make relevant calculations for each ticker to get current recommendations on selling/buying

            # Get an updated dataframe + names of the signal columns added
            data, selectedSignals = make_calculations(data, signalDict)

            # Get an overall buy/sell/wait recommendation based on the signals selected
            rec = data.loc[data.index[-1], "Final Rec"]

            # Get the number of days since the current recommendation became active
            daysSinceChange = data.loc[data.index[-1], "Days_Since_Change"]

            closingPrice = data["Close"].iloc[-1]

            # Check if an SMA column has already been added, and add one if it has not been
            data, smaCol = check_and_add_sma(data)

            smaPeriods = [7, 30, 90]
            smaChanges = []

            # Get the SMA changes for the ticker to show how much on average the price has dropped/increased
            # over the number of days indicated in the smaPeriods list above
            for noDays in smaPeriods:
                smaValue = get_previous_sma(data, smaCol, noDays)
                smaChanges.append(calculate_price_dif(closingPrice, smaValue)[1] + "%")

            # Format the closing price for each ticker for table display
            closingPrice = format_float(closingPrice)

            # Prepare a graph for each ticker
            data = adjust_start(data, startDateDatetime)
            graph = make_graph(data, ticker, selectedSignals, 600, 800)
            watchlistItem["graph"] = graph

            # Create a list of all the latest results for the signals saved
            signalResults = []
            for signal in selectedSignals:
                signalResults.append(format_float(data.loc[data.index.max()][signal]))

            # Create a dataframe with teh watchlist data for each ticker

            tickerHtml = f"<span class='watchlist-ticker'>{ticker}</span>"
            graphButtonHtml = f"<button class = 'graph-button' data-ticker={ticker}>See graph</button>"
            removeButtonHtml = f"<button class = 'remove-ticker-button' data-ticker_id={tickerId}>Remove</button>"
            tableEntries = \
                [tickerHtml, rec, daysSinceChange, closingPrice] \
                + smaChanges + signalResults + [graphButtonHtml, removeButtonHtml]
            # ['''<a href="{% url 'graph' %}" target="blank"> Graph </a>''']

            watchlistItem["resultTable"] = pd.DataFrame([tableEntries],
                                                         columns=['Ticker',
                                                                  'Analysis Outcome',
                                                                  'Days Since Trend Change',
                                                                  'Closing Price',
                                                                  '1 Week Change',
                                                                  '1 Month Change',
                                                                  '3 Months Change'] + selectedSignals + ["Graph"] +
                                                                 ["Remove From Watchlist?"])

            watchedTickers.append(watchlistItem)

        # Create a joint table with recommendations for each ticker to be displayed on the watchlist page
        jointTable = pd.DataFrame(columns=['Ticker',
                                           'Analysis Outcome',
                                           'Days Since Trend Change',
                                           'Closing Price',
                                           '1 Week Change',
                                           '1 Month Change',
                                           '3 Months Change'] + selectedSignals + ["Graph"] +
                                          ["Remove From Watchlist?"])
        for elt in watchedTickers:
            jointTable = pd.concat([jointTable, elt["resultTable"]], axis=0)

        jointTable.set_index("Ticker", inplace=True)
        jointTable.sort_values(by=['Days Since Trend Change', 'Ticker'], inplace=True)
        jointTable.rename_axis(None, inplace=True)

        htmlResultTable = jointTable.to_html(col_space=30, bold_rows=True, classes=["table", "result_table"],
                                             justify="left",
                                             escape=False)

    return render(request, "stock_screener/watchlist.html",
                  {'watched_tickers': watchedTickers, "htmlResultTable": htmlResultTable,
                   "signalTable": signalTable})


@login_required
def backtester(request):
    if request.method == "GET":
        user = request.user
        return render(request, "stock_screener/backtester.html", {"stockForm": BacktestForm(user)})

    if request.method == "POST":
        if 'tickers' in request.POST:
            backtestForm = BacktestForm(request.user, request.POST)

            # Get all the form data
            if backtestForm.is_valid():
                signalDict = {}

                for k in constructorFields:
                    signalDict[k] = backtestForm.cleaned_data[k]

                days_to_buy = backtestForm.cleaned_data["days_to_buy"]
                days_to_sell = backtestForm.cleaned_data["days_to_sell"]
                buy_price_adjustment = backtestForm.cleaned_data["buy_price_adjustment"]
                sell_price_adjustment = backtestForm.cleaned_data["sell_price_adjustment"]
                num_years = backtestForm.cleaned_data["num_years"]

                tickers = backtestForm.cleaned_data['tickers']

                if "ALL" in tickers:
                    tickers = sorted([o.ticker for o in SavedSearch.objects.filter(user=request.user)])

                # Calculating the start date according to client requirements
                endDate = date.today()
                startDate = endDate + relativedelta(years=-int(num_years))
                startDateInternal = startDate + relativedelta(months=-12)
                startDateDatetime = datetime.combine(startDate, datetime.min.time())

                # getting stocks data from S3
                existingStocks = read_csv_from_S3(bucket, "Stocks")

                # if no signals have been selected, remind the user to select signals
                if not (signalDict['ma']
                        or signalDict['psar']
                        or signalDict['adx']
                        or signalDict['srsi']
                        or signalDict['macd']):
                    context = {
                        "message": "Please select the signals to back test",
                        "stockForm": BacktestForm(request.user)
                    }
                    return render(request, "stock_screener/backtester.html", context)

                elif signalDict['adx'] and not (
                        signalDict['ma'] or signalDict['psar'] or signalDict['srsi'] or signalDict['macd']):
                    context = {
                        "message": "Please add another signal - ADX alone does not provide buy/sell recommendations",
                        "stockForm": BacktestForm(request.user)
                    }
                    return render(request, "stock_screener/backtester.html", context)

                allResults = {}
                allDetails = []
                averageIndTimesBetweenTransactions = []
                averageIndTimesHoldingStock = []

                for ticker in tickers:
                    # Preparing a dataframe for the period of time indicated by the user + 12 months for calculations
                    stock = existingStocks[ticker].copy().loc[startDateInternal:, :]

                    # removing NaN values from the stock data
                    stock.dropna(how="all", inplace=True)

                    # converting column data types to float
                    stock = stock.apply(pd.to_numeric)

                    # adding columns with calculations for the selected signals
                    stock, selectedSignals = make_calculations(stock, signalDict)

                    stock = adjust_start(stock, startDateDatetime)

                    # preparing backtesting information for the ticker
                    backtestResult, backtestDataFull = backtest_signal(stock,
                                                                       format_outcome=False,
                                                                       days_to_buy=days_to_buy,
                                                                       days_to_sell=days_to_sell,
                                                                       buy_price_adjustment=buy_price_adjustment,
                                                                       sell_price_adjustment=sell_price_adjustment)

                    # Creating a dictionary of profits/losses for individual tickers
                    allResults[ticker] = backtestResult

                    # if backtesting returned a dataframe with buy/sell prompts:
                    if backtestDataFull is not None:
                        # create a smaller DataFrame with the relevant column titles
                        backtestData = backtestDataFull.loc[:, ["Close", "Final Rec", "Price After Delay",
                                                                "Adjusted Price After Delay", "Profit/Loss"]]
                        backtestData.reset_index(inplace=True)
                        backtestData.columns = ["Date", "Closing Price", "Recommendation", "Price After Delay",
                                                "Adjusted Price After Delay", "Profit/Loss"]

                        numTransactions = len(backtestData.index)

                        # if there is more than 1 transaction in the backtest DataFrame
                        if numTransactions > 1:
                            daysBetweenStockTransactions = []
                            daysHoldingStock = []

                            # get the number of days between each two transactions,
                            # append results to the list for the stock
                            for i in range(1, numTransactions):
                                daysBetween2Transactions = (backtestData.Date[i] - backtestData.Date[i - 1]).days
                                daysBetweenStockTransactions.append(daysBetween2Transactions)

                                if backtestData.loc[i - 1, "Recommendation"] == "Buy":
                                    daysHoldingStock.append(daysBetween2Transactions)

                            averageTimeBetweenStockTransactions = round(
                                sum(daysBetweenStockTransactions) / (numTransactions - 1), 2)
                            averageIndTimesBetweenTransactions.append(averageTimeBetweenStockTransactions)

                            averageTimeHoldingStock = round(sum(daysHoldingStock) / len(daysHoldingStock), 2)
                            averageIndTimesHoldingStock.append(averageTimeHoldingStock)

                        # if only one ("buy") transaction has taken place
                        else:
                            averageTimeBetweenStockTransactions = None
                            averageTimeHoldingStock = None

                        # prepare an individual backtesting table per stock
                        indTable = backtestData.to_html(col_space=20, bold_rows=True, classes="table",
                                                        justify="left", index=False)

                    # If backtest returns no data (sell/buy prompts not generated by teh signal selected)
                    else:
                        numTransactions = None
                        averageTimeBetweenStockTransactions = None
                        averageTimeHoldingStock = None
                        indTable = "The selected signal has not generated a sufficient number " \
                                   "of buy/sell recommendations for this ticker"

                    # Prepare details and table to be displayed per ticker
                    allIndTickerDetails = (ticker, numTransactions, averageTimeBetweenStockTransactions,
                                           averageTimeHoldingStock, indTable)

                    # Prepare a list of all ticker info and tables to iterate through
                    allDetails.append(allIndTickerDetails)

                # Calculate average time between transactions for all the selected stocks
                if len(averageIndTimesBetweenTransactions) > 0:
                    overallAverageTimeBetweenTransactions = round(
                        sum(averageIndTimesBetweenTransactions) / len(averageIndTimesBetweenTransactions), 2)
                else:
                    overallAverageTimeBetweenTransactions = None

                if len(averageIndTimesHoldingStock) > 0:
                    overallAverageTimeHoldingStock = round(
                        sum(averageIndTimesHoldingStock) / len(averageIndTimesHoldingStock), 2)
                else:
                    overallAverageTimeBetweenTransactions = None

                # Preparing a main joint table with the results of backtesting
                backtesterTable = pd.DataFrame.from_dict(allResults, orient="index")
                backtesterTable.reset_index(inplace=True)
                backtesterTable.columns = ["Ticker", "Profit/Loss"]
                backtesterTable["Profit/Loss"] = backtesterTable["Profit/Loss"].apply(
                    lambda x: (format_float(x) + " %"))

                backtesterTable["Details"] = ""
                for i in range(backtesterTable.index.max() + 1):
                    nextTicker = backtesterTable.loc[i, "Ticker"]
                    backtesterTable.loc[i, "Details"] = \
                        f"<button class = 'ind_outcome_button' data-ticker={nextTicker}>See details</button>"

                htmlJointTable = backtesterTable.to_html(col_space=[150, 200, 150], bold_rows=True,
                                                         classes=["table", "backtest_table"],
                                                         escape=False, index=False)

                overallResult = calc_average_percentage(allResults.values())
                print(allResults)

                context = {
                    "overallResult": overallResult,
                    "htmlJointTable": htmlJointTable,
                    "allDetails": allDetails,
                    "overallAverageTimeBetweenTransactions": overallAverageTimeBetweenTransactions,
                    "overallAverageTimeHoldingStock": overallAverageTimeHoldingStock
                }

                return render(request, "stock_screener/backtester.html", context)

# def graph(request):
# return render(request, "stock_screener/graph.html")
