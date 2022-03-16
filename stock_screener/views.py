from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import User, SavedSearch, SignalConstructor
from django.db import IntegrityError
from .forms import StockForm
from .utils import read_csv_from_S3, adjust_start, make_graph, get_price_change, get_current_tickers_info, \
    upload_csv_to_S3, stock_tidy_up, prepare_ticker_info_update, get_company_name_from_yf, get_previous_sma, \
    calculate_price_dif, format_float
from .calculations import make_calculations
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import pandas as pd
import yfinance as yf
import ta
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

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
            # Get all the form data
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

                endDate = date.today()
                startDate = endDate + relativedelta(months=-numMonths)
                startDateInternal = startDate + relativedelta(months=-6)
                startDateDatetime = datetime.combine(startDate, datetime.min.time())

                selectedSignals = []
                signalResults = []
                height = 575
                width = 840

                existingStocks = read_csv_from_S3(bucket, "Stocks")
                tickerInfo = get_current_tickers_info(bucket)
                tickerList = list(tickerInfo.index)

                if ticker not in tickerList:
                    stock = yf.download(ticker, start=startDateInternal, end=endDate)
                    print(stock.tail())
                    if stock.empty:
                        message = f"Details for ticker {ticker} cannot be found"
                        context = {
                            "message": message,
                            "stockForm": StockForm
                        }
                        return render(request, "stock_screener/index.html", context)
                    else:
                        print("Data downloaded in full")
                        tickerName = get_company_name_from_yf(ticker)
                        tickerInfo = prepare_ticker_info_update(tickerInfo, ticker, tickerName)
                        upload_csv_to_S3(bucket, tickerInfo, "TickersInfo")
                        updatedStock = stock_tidy_up(stock, ticker)
                        updatedStocks = pd.concat([existingStocks, updatedStock], axis=1)
                        upload_csv_to_S3(bucket, updatedStocks, "Stocks")
                        # stock = updatedStocks[ticker]
                        tickerList = list(tickerInfo.index)

                else:
                    print("reading data and preparing graph")
                    stock = existingStocks[ticker].copy()

                tickerName = tickerInfo.loc[ticker]["Name"]
                stock.dropna(how="all", inplace=True)
                signals = [ma, maS, maL, maWS, maWL, psar, psarAF, psarMA, adx, adxW, adxL, srsi, srsiW, srsiSm1,
                           srsiSm2, srsiOB, srsiOS, macd, macdS, macdF, macdSm]

                # if no signals are selected:
                if not (ma or psar or adx or srsi or macd):
                    stock = stock.reset_index()
                    rec = "No signals selected"
                    daysSinceChange = "n/a"

                else:
                    stock, selectedSignals = make_calculations(stock, signals)
                    rec = stock.loc[stock.index[-1], "Final Rec"]  # .lower()
                    daysSinceChange = stock.loc[stock.index[-1], "Days_Since_Change"]

                for column in stock.columns:
                    if column.startswith("SMA"):
                        smaAdded = True
                        smaCol = column
                    else:
                        smaAdded = False

                if not smaAdded:
                    stock["Table SMA"] = ta.trend.sma_indicator(stock["Close"], window=15)
                    smaCol = "Table SMA"

                latestDate = stock["Date"].max()
                sma1 = get_previous_sma(stock, smaCol, latestDate, 7)
                sma2 = get_previous_sma(stock, smaCol, latestDate, 30)
                sma3 = get_previous_sma(stock, smaCol, latestDate, 90)

                closingPrice, priceChange = get_price_change(stock)

                change1 = calculate_price_dif(closingPrice, sma1)[1] + "%"
                change2 = calculate_price_dif(closingPrice, sma2)[1] + "%"
                change3 = calculate_price_dif(closingPrice, sma3)[1] + "%"

                stock = adjust_start(stock, startDateDatetime)
                graph = make_graph(stock, ticker, selectedSignals, height, width)

                print(selectedSignals)
                for signal in selectedSignals:
                    signalResults.append(format_float(stock.loc[stock.index.max()][signal]))

                data = [rec,
                        daysSinceChange,
                        change1,
                        change2,
                        change3] + signalResults

                resultTable = pd.DataFrame([data],
                                           columns=['Analysis Outcome',
                                                    'Days Since Trend Change',
                                                    '1 Week Change',
                                                    '1 Month Change',
                                                    '3 Months Change'] + selectedSignals)
                resultTable.set_index('Analysis Outcome', inplace=True)
                resultTable = resultTable.transpose()
                # resultTable.rename_axis(None, inplace=True)
                htmlResultTable = resultTable.to_html(col_space=30, bold_rows=True, classes="table", justify="left")

                watchlisted = False
                tickerID = None
                constructorAdded = False
                savedConstructor = None
                newSignal = None

                if request.user.is_authenticated:
                    searchObj = SavedSearch.objects.filter(user=request.user, ticker=ticker)
                    if len(searchObj):
                        watchlisted = True
                        tickerID = searchObj[0].id

                    constructorObj = SignalConstructor.objects.filter \
                        (user=request.user)
                    if len(constructorObj):
                        savedConstructor = constructorObj[0]

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
                print(newSignal)

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

            # can i pass it to html as an object instead?
            for item in watchlist:
                ticker = item.ticker
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

                for column in data.columns:
                    if column.startswith("SMA"):
                        smaAdded = True
                        smaCol = column
                    else:
                        smaAdded = False

                if not smaAdded:
                    data["Table SMA"] = ta.trend.sma_indicator(data["Close"], window=15)
                    smaCol = "Table SMA"

                latestDate = data["Date"].max()
                sma1 = get_previous_sma(data, smaCol, latestDate, 7)
                sma2 = get_previous_sma(data, smaCol, latestDate, 30)
                sma3 = get_previous_sma(data, smaCol, latestDate, 90)

                closingPrice, priceChange = get_price_change(data)

                change1 = calculate_price_dif(closingPrice, sma1)[1] + "%"
                change2 = calculate_price_dif(closingPrice, sma2)[1] + "%"
                change3 = calculate_price_dif(closingPrice, sma3)[1] + "%"

                closingPrice = format_float(closingPrice)
                data = adjust_start(data, startDateDatetime)
                graph = make_graph(data, ticker, selectedSignals, 600, 800)
                watchlist_item["graph"] = graph


                signalResults = []
                print(selectedSignals)
                for signal in selectedSignals:
                    signalResults.append(format_float(data.loc[data.index.max()][signal]))

                tableEntries = \
                    [ticker,
                     watchlist_item["rec"],
                     watchlist_item["daysSinceChange"],
                     closingPrice,
                     change1,
                     change2,
                     change3] \
                    + signalResults + [f"<button class = 'graph-button' data-ticker={ticker}>See graph</button>"]
                        #'''<a href="https://www.google.co.uk/" target="blank"> Graph </a>''']

                watchlist_item["resultTable"] = pd.DataFrame([tableEntries],
                                                             columns=['Ticker',
                                                                      'Analysis Outcome',
                                                                      'Days Since Trend Change',
                                                                      'Closing Price',
                                                                      '1 Week Change',
                                                                      '1 Month Change',
                                                                      '3 Months Change'] + selectedSignals + ["Graph"])

                # resultTable.set_index('Analysis Outcome', inplace=True)
                watched_tickers.append(watchlist_item)
            jointTable = pd.DataFrame(columns=['Ticker',
                                               'Analysis Outcome',
                                               'Days Since Trend Change',
                                               'Closing Price',
                                               '1 Week Change',
                                               '1 Month Change',
                                               '3 Months Change'] + selectedSignals + ["Graph"])
            for elt in watched_tickers:
                jointTable = pd.concat([jointTable, elt["resultTable"]], axis=0)

            jointTable.set_index("Ticker", inplace=True)
            jointTable.sort_values(by=['Days Since Trend Change', 'Ticker'], inplace=True)
            jointTable.rename_axis(None, inplace=True)

            htmlResultTable = jointTable.to_html(col_space=30, bold_rows=True, classes="table", justify="left",
                                                 escape=False)

        return render(request, "stock_screener/watchlist.html",
                      {'watched_tickers': watched_tickers, "htmlResultTable": htmlResultTable})

