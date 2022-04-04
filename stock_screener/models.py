from django.db import models
from django.contrib.auth.models import AbstractUser
import django.utils


class User(AbstractUser):
    pass


class SavedSearch(models.Model):
    ticker = models.CharField(max_length=5)
    ticker_full = models.CharField(max_length=20)
    date = models.DateTimeField(default=django.utils.timezone.now)
    notes = models.TextField(max_length=500, blank=True)
    user = models.ForeignKey("User", on_delete=models.CASCADE, related_name="watchlist")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['ticker', 'user'], name="unique_searches")
        ]

    def serialize(self):
        return {
            "id": self.id,
            "ticker": self.ticker,
            "ticker_full": self.ticker_full,
            "user": self.user.username,
            "date": self.date,
            "notes": self.notes
        }

    def __str__(self):
        return f"{self.ticker} on {self.date}, watched by {self.user}"


class SignalConstructor(models.Model):
    ma = models.BooleanField(default=False)
    maS = models.CharField(
        max_length=3,
        choices=[('SMA', 'Simple Moving Average'),
                 ('EMA', 'Exponential Moving Average')],
        default='SMA')

    maL = models.CharField(
        max_length=3,
        choices=[('SMA', 'Simple Moving Average'),
                 ('EMA', 'Exponential Moving Average')],
        default='SMA')
    maWS = models.IntegerField(default=15)
    maWL = models.IntegerField(default=25)

    psar = models.BooleanField(default=False)
    psarAF = models.FloatField(default=0.02)
    psarMA = models.FloatField(default=0.2)

    adx = models.BooleanField(default=False)
    adxW = models.IntegerField(default=14)
    adxL = models.IntegerField(default=20)

    srsi = models.BooleanField(default=False)
    srsiW = models.IntegerField(default=13)
    srsiSm1 = models.IntegerField(default=3)
    srsiSm2 = models.IntegerField(default=3)
    srsiOB = models.FloatField(default=0.8)
    srsiOS = models.FloatField(default=0.2)

    macd = models.BooleanField(default=False)
    macdF = models.IntegerField(default=12)
    macdS = models.IntegerField(default=26)
    macdSm = models.IntegerField(default=210)

    user = models.ForeignKey("User", on_delete=models.CASCADE, related_name="savedSignal", blank=True, null=True)
    customName = models.CharField(max_length=15, default="Custom")

    def __str__(self):
        listRep = []
        if self.ma:
            listRep.append(f"{self.maS} {self.maWS}, {self.maL} {self.maWL}")
        if self.psar:
            listRep.append(f"PSAR {self.psarAF} {self.psarMA}")
        if self.adx:
            listRep.append(f"ADX {self.adxW} {self.adxL}")
        if self.srsi:
            listRep.append(f"SRSI {self.srsiW} {self.srsiSm1} {self.srsiSm2} {self.srsiOB} {self.srsiOS}")
        if self.macd:
            listRep.append(f"MACD {self.macdF} {self.macdS} {self.macdSm}")

        return "+".join(listRep)
