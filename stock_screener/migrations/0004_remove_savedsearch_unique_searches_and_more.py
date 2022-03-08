# Generated by Django 4.0.2 on 2022-03-08 12:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock_screener', '0003_signalconstructor_users'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='savedsearch',
            name='unique_searches',
        ),
        migrations.RenameField(
            model_name='savedsearch',
            old_name='stock',
            new_name='ticker',
        ),
        migrations.RenameField(
            model_name='savedsearch',
            old_name='stock_full',
            new_name='ticker_full',
        ),
        migrations.AddConstraint(
            model_name='savedsearch',
            constraint=models.UniqueConstraint(fields=('ticker', 'user'), name='unique_searches'),
        ),
    ]
