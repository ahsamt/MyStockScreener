# Generated by Django 4.0.2 on 2022-03-09 13:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock_screener', '0004_remove_savedsearch_unique_searches_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='signalconstructor',
            name='users',
        ),
        migrations.AddField(
            model_name='signalconstructor',
            name='customName',
            field=models.CharField(default='Custom', max_length=15),
        ),
    ]
