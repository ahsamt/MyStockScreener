from django import forms


class StockForm(forms.Form):
    ticker = forms.CharField(label='Stock name', max_length=5,
                            widget=forms.TextInput(attrs={'autofocus': True, 'placeholder': 'AAPL'}))
    smas = forms.BooleanField(label='Simple Moving Average (SMA) - short window', required=False)
    smasWS = forms.IntegerField(label='SMA window size - short', max_value=100, initial="15",
                                widget=forms.NumberInput(attrs={'style': 'width:9ch'}))


    smal = forms.BooleanField(label='Simple Moving Average (SMA) - long window', required=False)
    smalWS = forms.IntegerField(label='SMA window size - long', max_value=100, initial="45",
                                widget=forms.NumberInput(attrs={'style': 'width:9ch'}))


    ema = forms.BooleanField(label='Exponential Moving Average (EMA)', required=False)
    emaW = forms.IntegerField(label='EMA window size', max_value=100, initial="45",
                              widget=forms.NumberInput(attrs={'style': 'width:9ch'}))


    psar = forms.BooleanField(label='Parabolic Stop And Reverse (Parabolic SAR)', required=False)
    psarAF = forms.FloatField(label='Parabolic SAR Acceleration Factor (AF)', max_value=100, initial="0.02",
                              widget=forms.NumberInput(attrs={'style': 'width:9ch'}))
    psarMA = forms.FloatField(label='Parabolic SAR Maximum Acceleration (MA)', max_value=100, initial="0.2",
                              widget=forms.NumberInput(attrs={'style': 'width:9ch'}))


    adx = forms.BooleanField(label='Average Directional Movement Index (ADX)', required=False)
    adxW = forms.IntegerField(label='ADX window', max_value=100, initial="18",
                              widget=forms.NumberInput(attrs={'style': 'width:9ch'}))


    srsi = forms.BooleanField(label='Stochastic RSI (SRSI)', required=False)
    srsiW = forms.IntegerField(label='SRSI window', max_value=100, initial="21",
                               widget=forms.NumberInput(attrs={'style': 'width:9ch'}))
    srsiSm1 = forms.IntegerField(label='SRSI smooth 1', max_value=100, initial="3",
                                 widget=forms.NumberInput(attrs={'style': 'width:9ch'}))
    srsiSm2 = forms.IntegerField(label='SRSI smooth 2', max_value=100, initial="3",
                                 widget=forms.NumberInput(attrs={'style': 'width:9ch'}))

    macd = forms.BooleanField(label='Moving Average Convergence Divergence (MACD)', required=False)
    macdF = forms.IntegerField(label='MACD fast', max_value=100, initial="24",
                               widget=forms.NumberInput(attrs={'style': 'width:9ch'}))
    macdS = forms.IntegerField(label='MACD slow', max_value=100, initial="52",
                               widget=forms.NumberInput(attrs={'style': 'width:9ch'}))
    macdSm = forms.IntegerField(label='MACD smoothing period', max_value=100, initial="9",
                                widget=forms.NumberInput(attrs={'style': 'width:9ch'}))
