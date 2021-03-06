import json

import pandas as pd
import yfinance as yf
from dateutil.relativedelta import relativedelta
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from .calculations import make_calculations
from .forms import StockForm, BacktestForm, suggestedTickers
from .models import User, SavedSearch, SignalConstructor
from .utils import adjust_start, make_graph, upload_csv_to_s3, stock_tidy_up, \
    prepare_ticker_info_update, get_company_details_from_yf, get_previous_sma, \
    calculate_price_dif, format_float, backtest_signal, prepare_signal_table, calc_average_percentage, \
    check_and_add_sma, constructorFields, compare_signals, get_date_within_df, get_saved_stocks_details, \
    get_start_dates, read_csv_from_s3

bucket = 'stockscreener-data'
recColours = {'Wait': 'grey', 'Buy': 'green', 'Sell': 'bright-red'}
recColoursWatchlist = {'Wait': 'grey', 'Buy': 'green-circle', 'Sell': 'bright-red-circle'}


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

                if signalDict['adx'] and not (
                        signalDict['ma'] or signalDict['psar'] or signalDict['srsi'] or signalDict['macd']):
                    context = {
                        "message": "Please add another signal - ADX alone does not provide buy/sell recommendations",
                        "stockForm": stockForm
                    }
                    return render(request, "stock_screener/index.html", context)

                # Calculating the start date according to client requirements

                calcsStartDate, displayStartDateDt = get_start_dates(numMonths)

                signalResults = []

                # setting height and width for the graph
                height = 575
                width = 840

                # getting stocks data from S3
                existingStocks = read_csv_from_s3(bucket, "Stocks")
                tickerList = set(existingStocks.columns.get_level_values(0))

                #getting previously saved tickers details table
                tickerInfo = get_saved_stocks_details()

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

                        # prepare stock data for concatenation with the table on S3
                        updatedStock = stock_tidy_up(stock, ticker)

                        # update stock data table and upload back on S3
                        updatedStocks = pd.concat([existingStocks, updatedStock], axis=1)
                        upload_csv_to_s3(bucket, updatedStocks, "Stocks")
                else:
                    # print("reading S3 data and preparing graph")
                    print(existingStocks[ticker].tail())
                    stock = existingStocks[ticker].copy()

                # check if we have company details in local csv file:
                if ticker not in tickerInfo.index:
                    # get company info for the ticker and save info on S3
                    # This needs to be updated to save changes to local csv!!!!
                    tickerName, sector, country = get_company_details_from_yf(ticker)
                    tickerInfo = prepare_ticker_info_update(tickerInfo, ticker, tickerName, sector, country)
                    tickerInfo.to_csv("stock_screener/Tickers_details.csv")

                # getting full company name for the selected ticker
                tickerName = tickerInfo.loc[ticker]["Name"]
                sector = tickerInfo.loc[ticker]["Sector"]
                country = tickerInfo.loc[ticker]["Country"]

                # Getting the slice of the data starting from 18 months back
                # (12 required for display + 12 extra for analysis)
                calcsStartDate = get_date_within_df(stock, calcsStartDate)
                stock = stock.loc[calcsStartDate:, :]

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
                    recHtml = rec
                    daysSinceChange = "n/a"

                # if any of the signals are selected:
                else:
                    signalSelected = True

                    # adding columns with calculations for the selected signals
                    stock, selectedSignals = make_calculations(stock, signalDict)

                    # getting info for the result table
                    rec = stock["Final Rec"].iloc[-1]
                    recHtml = f"<span class={recColours[rec]} rec>{rec}</span>"
                    daysSinceChange = stock["Days_Since_Change"].iloc[-1]

                # getting last closing price for the ticker + price change information to display in the results window

                closingPrice = stock["Close"].iloc[-1]
                previousPrice = stock["Close"].iloc[-2]
                priceChange = calculate_price_dif(closingPrice, previousPrice)

                # Check if an SMA column has already been added, and add one if it has not been
                stock, smaCol = check_and_add_sma(stock)

                smaPeriods = [7, 30, 90]
                smaChanges = []

                # getting the SMA value changes for the ticker
                # going back the number of days indicated in the smaPeriods list
                for noDays in smaPeriods:
                    smaValue = get_previous_sma(stock, smaCol, noDays)
                    if smaValue is None:
                        smaChanges.append("No stock data")
                    else:
                        smaChanges.append(calculate_price_dif(closingPrice, smaValue) + "%")

                # adjusting the start date according to client requirements and preparing the graph
                stock = adjust_start(stock, displayStartDateDt)

                graph1, graph2, graph3, graph4 = make_graph(stock, ticker, selectedSignals, height, width,
                                                            srsi_overbought_limit=signalDict["srsiOB"],
                                                            srsi_oversold_limit=signalDict["srsiOS"],
                                                            adx_limit=signalDict["adxL"])

                if signalSelected:
                    # preparing backtesting information to be shown on search page
                    backtestResult, backtestDataFull = backtest_signal(stock)
                    signalSelected = True

                    if backtestDataFull is not None:
                        backtestData = backtestDataFull.loc[:, ["Close", "Final Rec", "Profit/Loss"]]
                        backtestData.reset_index(inplace=True)
                        backtestData.columns = ["Date", "Price", "Action", "Profit/Loss"]


                        htmlBacktestTable = backtestData.to_html(col_space=30, bold_rows=True,
                                                                 classes=["table", "backtesting_table"],
                                                                 justify="left", index=False)
                    else:
                        htmlBacktestTable = None

                else:
                    backtestResult, htmlBacktestTable = 0, None
                    signalSelected = False

                # Preparing the results table to be shown on search page

                for signal in selectedSignals:
                    signalResults.append(format_float(stock.loc[stock.index.max()][signal]))
                data = [recHtml, daysSinceChange, format_float(closingPrice), priceChange+"%"] + \
                       smaChanges + signalResults
                resultTable = pd.DataFrame([data],
                                           columns=['Analysis Outcome',
                                                    'Trading Days Since Trend Change',
                                                    'Last Closing Price, USD',
                                                    'Change Since Previous Trading Day',
                                                    '1 Week SMA Change',
                                                    '1 Month SMA Change',
                                                    '3 Months SMA Change'] + selectedSignals)
                resultTable.set_index('Analysis Outcome', inplace=True)
                resultTable = resultTable.transpose()
                htmlResultTable = resultTable.to_html(col_space=30, bold_rows=True, classes=["table", "stock_table"],
                                                      justify="left", escape=False)

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
                        constructorAdded = compare_signals(savedConstructor, signalDict)

                context = {
                    "ticker": ticker,
                    "tickerName": tickerName,
                    "sector": sector,
                    "country": country,
                    "graph1": graph1,
                    "graph2": graph2,
                    "graph3": graph3,
                    "graph4": graph4,
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
    calcsStartDate, displayStartDateDt = get_start_dates(numMonths)

    if request.method == "GET":
        watchedTickers = []
        watchlistObjects = SavedSearch.objects.filter(user=request.user)
        if len(watchlistObjects) == 0:
            return render(request, "stock_screener/watchlist.html",
                          {"empty_message": "You do not have any tickers added to your watchlist"})

        allStocksFull = read_csv_from_s3(bucket, "Stocks")
        calcsStartDate = get_date_within_df(allStocksFull, calcsStartDate)

        # Getting the slice of the data starting from 18 months back (12 required for display + 12 extra for analysis)
        allStocks = allStocksFull.loc[calcsStartDate:, :]

        # Check if the user has a signal saved in their profile
        try:
            signal = SignalConstructor.objects.get(user=request.user)
            signalId = signal.id

        except SignalConstructor.DoesNotExist:
            return render(request, "stock_screener/watchlist.html",
                          {"empty_message": "Please create and save a signal on the 'Search' page to view "
                                            "recommendations for your watchlist"})

        # Converting the saved signal object to dictionary
        signalDict = vars(signal)

        # prepare a table to display the saved signal to the user
        signalTable = prepare_signal_table(signalDict)

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
            rec = data["Final Rec"].iloc[-1]
            recHtml = f"<span class={recColoursWatchlist[rec]} rec>{rec}</span>"

            # Get the number of days since the current recommendation became active
            daysSinceChange = data["Days_Since_Change"].iloc[-1]

            closingPrice = data["Close"].iloc[-1]

            # Check if an SMA column has already been added, and add one if it has not been
            data, smaCol = check_and_add_sma(data)

            smaPeriods = [7, 30, 90]
            smaChanges = []

            # Get the SMA changes for the ticker to show how much on average the price has dropped/increased
            # over the number of days indicated in the smaPeriods list above
            for noDays in smaPeriods:
                smaValue = get_previous_sma(data, smaCol, noDays)
                if smaValue is None:
                    smaChanges.append("No stock data")
                else:
                    smaChanges.append(calculate_price_dif(closingPrice, smaValue) + "%")

            # Format the closing price for each ticker for table display
            closingPrice = format_float(closingPrice)

            # Create a list of all the latest results for the signals saved
            signalResults = []
            for signal in selectedSignals:
                signalResults.append(format_float(data.loc[data.index.max()][signal]))

            # Create a dataframe with teh watchlist data for each ticker

            tickerHtml = f"<span class='watchlist-ticker'>{ticker}</span>"

            graphButtonHtml = f'<a href = "{reverse("display_graph", kwargs={"ticker_id": tickerId, "constructor_id": signalId})}" ' \
                              f'target = "_blank"><button class = "graph-button">Graph</button></a>'
            notesButtonHtml = f"<button class = 'notes-button' data-ticker={ticker}>Notes</button>"
            removeButtonHtml = f"<button class = 'remove-ticker-button' data-ticker_id={tickerId}>&#10005</button>"
            tableEntries = \
                [tickerHtml, recHtml, daysSinceChange, closingPrice] \
                + smaChanges + signalResults + [graphButtonHtml, notesButtonHtml, removeButtonHtml]

            tableColumns = ['Ticker',
                            'Analysis Outcome',
                            'Trading Days Since Trend Change',
                            'Closing Price',
                            '1 Week SMA Change',
                            '1 Month SMA Change',
                            '3 Months SMA Change'] + selectedSignals + ["Graph", "Notes", "Remove"]

            watchlistItem["resultTable"] = pd.DataFrame([tableEntries],
                                                        columns=tableColumns)

            watchedTickers.append(watchlistItem)

        # Create a joint table with recommendations for each ticker to be displayed on the watchlist page
        jointTable = pd.DataFrame(columns=tableColumns)
        for elt in watchedTickers:
            jointTable = pd.concat([jointTable, elt["resultTable"]], axis=0)
        jointTable.set_index("Ticker", inplace=True)
        jointTable.sort_values(by=['Trading Days Since Trend Change', 'Ticker'], inplace=True)
        jointTable.rename_axis(None, inplace=True)

        htmlResultTable = jointTable.to_html(col_space='80px', bold_rows=True, classes=["table", "result_table"],
                                             justify="left",
                                             escape=False)

    return render(request, "stock_screener/watchlist.html",
                  {'watched_tickers': watchedTickers, "htmlResultTable": htmlResultTable,
                   "signalTable": signalTable})


def backtester(request):
    if request.method == "GET":
        user = request.user

        if user.is_authenticated:
            if len(SavedSearch.objects.filter(user=request.user)) == 0:
                tickersMessage = "To use back tester with your preferred tickers, please add them to your watchlist first."

            else:
                tickersMessage = "To add more tickers to this back test, please add them to your watchlist first."
        else:
            tickersMessage = None
        return render(request, "stock_screener/backtester.html", {"stockForm": BacktestForm(user), "tickersMessage": tickersMessage})

    if request.method == "POST":
        user = request.user
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
                num_years = int(backtestForm.cleaned_data["num_years"])
                fee_per_trade = backtestForm.cleaned_data["fee_per_trade"]
                amount_to_invest = int(backtestForm.cleaned_data["amount_to_invest"])

                tickers = backtestForm.cleaned_data['tickers']

                if "ALL" in tickers:
                    if user.is_authenticated:
                        if len(SavedSearch.objects.filter(user=request.user)) > 0:
                            tickers = sorted([o.ticker for o in SavedSearch.objects.filter(user=request.user)])
                        else:
                            tickers = suggestedTickers
                    else:
                        tickers = suggestedTickers

                # Calculating the start date according to client requirements
                calcsStartDate, displayStartDateDt = get_start_dates(num_years * 12)

                # getting stocks data from S3
                existingStocks = read_csv_from_s3(bucket, "Stocks")

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

                signalSelected = True
                allResults = {}
                totalFinalAmount = 0
                allDetails = []
                averageIndTimesBetweenTransactions = []
                averageIndTimesHoldingStock = []
                averageNumbersOfTransactions = []

                for ticker in tickers:
                    # Preparing a dataframe for the period of time indicated by the user + 12 months for calculations
                    calcsStartDate = get_date_within_df(existingStocks[ticker], calcsStartDate)
                    stock = existingStocks[ticker].copy().loc[calcsStartDate:, :]

                    # removing NaN values from the stock data
                    stock.dropna(how="all", inplace=True)

                    # converting column data types to float
                    stock = stock.apply(pd.to_numeric)

                    # adding columns with calculations for the selected signals
                    stock, selectedSignals = make_calculations(stock, signalDict)

                    stock = adjust_start(stock, displayStartDateDt)

                    # preparing backtesting information for the ticker
                    backtestResult, backtestDataFull = backtest_signal(stock,
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
                        averageNumbersOfTransactions.append(numTransactions)

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

                            amountSpentOnFees = fee_per_trade * numTransactions
                            totalAmountRemaining = amount_to_invest * (1 + backtestResult / 100)
                            finalAmountRaw = totalAmountRemaining - amountSpentOnFees
                            finalAmount = format_float(finalAmountRaw)

                            result = round(backtestResult, 2)

                        # if only one ("buy") transaction has taken place
                        else:
                            averageTimeBetweenStockTransactions = "Insufficient number of transactions"
                            averageTimeHoldingStock = "Insufficient number of transactions"
                            finalAmount = amount_to_invest
                            finalAmountRaw = amount_to_invest
                            result = 0

                        # prepare an individual backtesting table per stock
                        indTable = backtestData.to_html(col_space=20, bold_rows=True, classes="table",
                                                        justify="left", index=False)

                    # If backtest returns no data (sell/buy prompts not generated by the signal selected)
                    else:
                        numTransactions = 0
                        averageTimeBetweenStockTransactions = "Insufficient number of transactions"
                        averageTimeHoldingStock = "Insufficient number of transactions"
                        finalAmount = amount_to_invest
                        finalAmountRaw = amount_to_invest
                        result = 0
                        averageNumbersOfTransactions.append(0)

                        indTable = "The selected signal has not generated a sufficient number " \
                                   "of buy/sell recommendations for this ticker"

                    indStats = {'Number of transactions': numTransactions,
                                'Average time between transactions (days': averageTimeBetweenStockTransactions,
                                'Average time holding stock (days)': averageTimeHoldingStock,
                                'Final amount': finalAmount}

                    indStatsTable = pd.DataFrame.from_dict(indStats, orient="index")
                    indStatsTable.reset_index(inplace=True)

                    htmlIndStatsTable = indStatsTable.to_html(col_space=[100, 100], bold_rows=True,
                                                              classes=["table", "ind_stats_table"],
                                                              escape=False, index=False, header=False)

                    # Prepare details and table to be displayed per ticker
                    allIndTickerDetails = {'ticker': ticker,
                                           'result': result,
                                           'htmlIndStatsTable': htmlIndStatsTable,
                                           'indTable': indTable}


                    # Prepare a list of all ticker info and tables to iterate through
                    allDetails.append(allIndTickerDetails)

                    # Add up the final amounts remaining for each ticker
                    totalFinalAmount += finalAmountRaw

                # Calculate total amount invested and profit or loss
                totalInvestedAmount = amount_to_invest * len(tickers)
                overallResult = round((totalFinalAmount/totalInvestedAmount * 100 - 100), 2)

                # Calculate average time between transactions for all the selected stocks
                if len(averageIndTimesBetweenTransactions) > 0:
                    overallAverageTimeBetweenTransactions = round(
                        sum(averageIndTimesBetweenTransactions) / len(averageIndTimesBetweenTransactions), 2)
                else:
                    overallAverageTimeBetweenTransactions = "No transactions identified"

                if len(averageIndTimesHoldingStock) > 0:
                    overallAverageTimeHoldingStock = round(
                        sum(averageIndTimesHoldingStock) / len(averageIndTimesHoldingStock), 2)
                else:
                    overallAverageTimeHoldingStock = "No transactions identified"

                # Preparing a table with general stats

                genStats = {'Average time between transactions (days)': overallAverageTimeBetweenTransactions,
                            'Average time holding stock (days)': overallAverageTimeHoldingStock,
                            'Average number of transactions': sum(averageNumbersOfTransactions) // len(
                                averageNumbersOfTransactions)}

                genStatsTable = pd.DataFrame.from_dict(genStats, orient="index")
                genStatsTable.reset_index(inplace=True)

                htmlGenStatsTable = genStatsTable.to_html(col_space=[300, 150], classes=["table", "gen_stats_table"],
                                                          escape=False, index=False, header=False)

                # Preparing a main joint table with the results of backtesting
                backtesterTable = pd.DataFrame.from_dict(allResults, orient="index")
                backtesterTable.reset_index(inplace=True)
                backtesterTable.columns = ["Ticker", "Profit/Loss"]
                backtesterTable["Profit/Loss"] = backtesterTable["Profit/Loss"].map(
                    lambda x: ("<span class = 'bright-red'>" + format_float(x) + "% </ span>" if x <= 0 else "<span class = 'green'>" + '+' + format_float(x) + "% </ span>"))



                backtesterTable["Details"] = ""
                for i in range(backtesterTable.index.max() + 1):
                    nextTicker = backtesterTable.loc[i, "Ticker"]
                    backtesterTable.loc[i, "Details"] = \
                        f"<button class = 'ind_outcome_button' data-ticker={nextTicker}>See details</button>"

                htmlJointTable = backtesterTable.to_html(col_space=[150, 150, 150], bold_rows=True,
                                                         classes=["table", "backtest_table"],
                                                         escape=False, index=False)



                # prepare a table to display the saved signal to the user
                signalTable = prepare_signal_table(signalDict)

                # Check if the user has a signal saved in their profile
                if user.is_authenticated:
                    try:
                        # checking if the user has previously saved any signal for their watchlist
                        constructorObj = SignalConstructor.objects.filter(user=request.user)

                        if len(constructorObj):
                            savedConstructor = constructorObj[0]
                            # checking if the signal user has previously saved
                            # matches the signal being used for the current search
                            constructorAdded = compare_signals(savedConstructor, signalDict)
                        else:
                            constructorAdded = False
                            savedConstructor = None

                    except SignalConstructor.DoesNotExist:
                        constructorAdded = False
                        savedConstructor = None
                else:
                    constructorAdded = False
                    savedConstructor = None

                context = {
                    "overallResult": overallResult,
                    "htmlJointTable": htmlJointTable,
                    "allDetails": allDetails,
                    "htmlGenStatsTable": htmlGenStatsTable,
                    "signalTable": signalTable,
                    "signalSelected": signalSelected,
                    "constructorAdded": constructorAdded,
                    "savedConstructor": savedConstructor,
                    "newSignal": signalDict,
                }

                return render(request, "stock_screener/backtester.html", context)


@login_required
def display_graph(request, ticker_id, constructor_id):
    numMonths = 12
    calcsStartDate, displayStartDateDt = get_start_dates(numMonths)

    if request.method == "GET":
        try:
            search_data = SavedSearch.objects.get(
                user=request.user, id=ticker_id)
        except SavedSearch.DoesNotExist:
            return render(request, "stock_screener/child_templates/graph.html",
                          {"error_message": "You do not have any saved ticker associated with this ID"})

        allStocksFull = read_csv_from_s3(bucket, "Stocks")

        # Getting the slice of the data starting from 18 months back (12 required for display + 12 extra for analysis)
        calcsStartDate = get_date_within_df(allStocksFull, calcsStartDate)
        allStocks = allStocksFull.loc[calcsStartDate:, :]

        signal = SignalConstructor.objects.get(user=request.user, id=constructor_id)

        # # Check if the user has a signal saved in their profile
        # try:
        #     signal = SignalConstructor.objects.get(user=request.user)
        #
        # except SignalConstructor.DoesNotExist:
        #     return render(request, "stock_screener/watchlist.html",
        #                   {"empty_message": "Please create and save a signal on the 'Search' page to view "
        #                                     "recommendations for your watchlist"})

        # Converting the saved signal object to dictionary
        signalDict = vars(signal)

        # prepare a table to display the saved signal to the user
        ticker = search_data.ticker

        # Creating a separate dataframe for each stock, dropping n/a values and converting data to numeric
        data = allStocks[ticker].copy()
        data.dropna(how="all", inplace=True)
        data = data.apply(pd.to_numeric)

        # make relevant calculations for each ticker to get current recommendations on selling/buying

        # Get an updated dataframe + names of the signal columns added
        data, selectedSignals = make_calculations(data, signalDict)

        # Prepare a graph for each ticker
        data = adjust_start(data, displayStartDateDt)
        graphs = list(make_graph(data, ticker, selectedSignals, 600, 870, srsi_overbought_limit=signalDict["srsiOB"],
                                                            srsi_oversold_limit=signalDict["srsiOS"],
                                                            adx_limit=signalDict["adxL"]))

    return render(request, "stock_screener/graph.html",
                  {"ticker": ticker, 'graphs': graphs})


def about(request):
    return render(request, "stock_screener/about.html")
