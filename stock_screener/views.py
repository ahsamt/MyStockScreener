from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from .models import User
from django.db import IntegrityError
from .forms import StockForm

signalOptions = sorted((
    ("SMAS", "Simple Moving Average (SMA) - short window"),
    ("SMAL", "Simple Moving Average (SMA) - long window"),
    ("EMA", " Exponential Moving Average (EMA)"),
    ("PSAR", "Parabolic Stop And Reverse (Parabolic SAR)"),
    ("ADX", "Average Directional Movement Index (ADX)"),
    ("SRSI", "Stochastic RSI (SRSI)"),
    ("MACD", "Moving Average Convergence Divergence (MACD)"),
))


def index(request):
    if request.method == "GET":
        return render(request, "stock_screener/index.html", {"stockForm": StockForm()})

    if request.method == "POST":
        if 'stock' in request.POST:
            stockForm = StockForm(request.POST)
            if stockForm.is_valid():
                stock = stockForm.cleaned_data['stock'].upper()

        return render(request, "stock_screener/index.html")


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
