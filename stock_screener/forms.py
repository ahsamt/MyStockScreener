from django import forms

from stock_screener.models import SavedSearch

ma1_choices = [('SMA', 'Simple Moving Average'), ('EMA', 'Exponential Moving Average')]
ma2_choices = [('SMA', 'Simple Moving Average'), ('EMA', 'Exponential Moving Average')]


class SignalForm(forms.Form):
    ma = forms.BooleanField(label='Moving Average', required=False)
    maS = forms.ChoiceField(label='Moving Average type (short)', required=False, choices=ma1_choices)
    maWS = forms.IntegerField(label='Short window length, days', min_value=1, max_value=220, initial="15",
                              widget=forms.NumberInput(attrs={'style': 'width:7ch'}))
    maL = forms.ChoiceField(label='Moving Average type (long)', required=False, choices=ma2_choices)

    maWL = forms.IntegerField(label='Long window length, days', min_value=1, max_value=220, initial="25",
                              widget=forms.NumberInput(attrs={'style': 'width:7ch'}))

    psar = forms.BooleanField(label='Parabolic SAR', required=False)
    psarAF = forms.FloatField(label='Acceleration Factor', min_value=0.01, max_value=1,
                              initial="0.02",
                              widget=forms.NumberInput(attrs={'style': 'width:7ch'}))
    psarMA = forms.FloatField(label='Maximum Acceleration', min_value=0.01, max_value=1,
                              initial="0.2",
                              widget=forms.NumberInput(attrs={'style': 'width:7ch'}))

    adx = forms.BooleanField(label='ADX', required=False)
    adxW = forms.IntegerField(label='Window length, days', min_value=1, max_value=220, initial="14",
                              widget=forms.NumberInput(attrs={'style': 'width:7ch'}))
    adxL = forms.IntegerField(label='Value limit', min_value=0, max_value=100, initial="20",
                              widget=forms.NumberInput(attrs={'style': 'width:7ch'}))

    srsi = forms.BooleanField(label='Stochastic RSI', required=False)
    srsiW = forms.IntegerField(label='Window length, days', min_value=1, max_value=220, initial="13",
                               widget=forms.NumberInput(attrs={'style': 'width:7ch'}))
    srsiSm1 = forms.IntegerField(label='Smooth 1', min_value=1, max_value=220, initial="3",
                                 widget=forms.NumberInput(attrs={'style': 'width:7ch'}))
    srsiSm2 = forms.IntegerField(label='Smooth 2', min_value=1, max_value=220, initial="3",
                                 widget=forms.NumberInput(attrs={'style': 'width:7ch'}))
    srsiOB = forms.FloatField(label='Overbought limit', min_value=0, max_value=100, initial="0.8",
                              widget=forms.NumberInput(attrs={'style': 'width:7ch'}))
    srsiOS = forms.FloatField(label='Oversold limit', min_value=0, max_value=100, initial="0.2",
                              widget=forms.NumberInput(attrs={'style': 'width:7ch'}))

    macd = forms.BooleanField(label='MACD', required=False)
    macdF = forms.IntegerField(label='Fast', min_value=1, max_value=220, initial="12",
                               widget=forms.NumberInput(attrs={'style': 'width:7ch'}))
    macdS = forms.IntegerField(label='Slow', min_value=1, max_value=220, initial="26",
                               widget=forms.NumberInput(attrs={'style': 'width:7ch'}))
    macdSm = forms.IntegerField(label='Smoothing period', min_value=1, max_value=220, initial="210",
                                widget=forms.NumberInput(attrs={'style': 'width:7ch'}))


class StockForm(SignalForm):
    ticker = forms.CharField(label='Stock name', max_length=30,
                             widget=forms.TextInput(attrs={'autofocus': True, 'placeholder': 'AAPL'}))

    # bb = forms.BooleanField(label="Bollinger Bands", required=False)
    # bbW = forms.IntegerField(label="Window length, days", min_value=1, max_value=220, initial=25,
    # widget=forms.NumberInput(attrs={'style': 'width:7ch'}))


class BacktestForm(SignalForm):
    days_to_buy = forms.IntegerField(label='Days to Complete a Buy Order', min_value=0, max_value=10, initial="0",
                                     widget=forms.NumberInput(attrs={'style': 'width:9ch'}))
    days_to_sell = forms.IntegerField(label='Days to Complete a Sell Order', min_value=0, max_value=10, initial="0",
                                      widget=forms.NumberInput(attrs={'style': 'width:9ch'}))

    buy_price_adjustment = forms.IntegerField(label='Days to Complete a Sell Order', min_value=0, max_value=10,
                                              initial="0",
                                              widget=forms.NumberInput(attrs={'style': 'width:9ch'}))
    sell_price_adjustment = forms.IntegerField(label='Days to Complete a Sell Order', min_value=0, max_value=10,
                                               initial="0",
                                               widget=forms.NumberInput(attrs={'style': 'width:9ch'}))

    num_years = forms.ChoiceField(label='Number of years this back test should cover', initial=1,
                                  choices=[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)])

    def __init__(self, user, *args, **kwargs):
        super(BacktestForm, self).__init__(*args, *kwargs)
        self.fields['tickers'] = forms.MultipleChoiceField(
            choices=([("ALL", "All watchlisted tickers")] + sorted([(o.ticker, o.ticker)
                                                                    for o in SavedSearch.objects.filter(user=user)])),
            widget=forms.CheckboxSelectMultiple, initial="ALL")
