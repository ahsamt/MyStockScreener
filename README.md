# Stock Screener


## About this project</h2>
StockScreener is designed to help you create your own customised signal for monitoring the performance of your watchlisted stocks. The signal can be back tested on financial data that goes back up to 5 years, and you can use custom parameters such as delaying order completion by a specified number of days, factoring in buy/sell price adjustment, specifying initial amount to be invested and taking into account trading fees.

The financial data for this project is stored in my personal S3 bucket and gets updated every night using yfinance and AWS Lambda. If you would like to run this project locally (rather than use the website linked above), you may wish to update the code so that it queries yfinance for each new stock instead of trying to access the S3 bucket. Alternatively, you can set up your own S3 bucket with the relevant financial information.

## Signals available

This StockScreener offers 5 signals you can combine to create your own bespoke signal

### Moving Average

The moving average (MA) is a simple technical analysis tool that smooths out price data by creating a constantly updated average price. The average is taken over a specific period of time (window).

A 'buy' signal is generated when a shorter-term moving average crosses above a longer-term moving average, and a 'sell' signal is generated when a short moving average crosses below a long moving average.</p>

A Simple moving average (SMA) is calculated by adding all the data for a specific time period and dividing the total by the number of days.
An Exponential moving average (EMA) assigns greater weight to the most recent data.</p>

### Parabolic SAR

Parabolic SAR (stop and reverse) is known as a momentum indicator and used to identify potential trend reversals when the price is in a strong uptrend or downtrend.
On a price chart, the Parabolic SAR appears as a series of dots placed either above or below the price, depending on the direction the price is moving.
A dot is placed below the price when it is trending upward ('buy' signal), and above the price when it is trending downward ('sell' signal). </p>

Increasing the Acceleration Factor means the indicator will more closely track the price, which means more trade signals and reversals will be identified. Decreasing the Acceleration Factor will result in the indicator moving slower, which means fewer trade signals and reversals will occur.
The Maximum Acceleration works the same in a way, but to a much lesser degree. The MA caps how quickly the indicator can accelerate during a strong price move. Changes in this setting will have less impact than changing the AF.

### ADX

The average direction index (ADX) is used to determine the strength of a trend. ADX uses an absolute value approach - it will quantify the strength of a trend irrespective of its direction.

The ADX gives you a reading that generally ranges between 0 and 50. The higher the reading, the stronger the trend. The lower the reading, the weaker the trend.</p>
By setting the Value Limit, you indicate how strong a trend needs to be in order to confirm ‘buy’ or ‘sell’ recommendations produced by another StockScreener signal.
The standard ADX time periods setting is 14, but many use the ADX with settings as low as 7 or as high as 30. Using a relatively high setting smooths out the average price action shown by the ADX line over a longer time frame, resulting in more reliable trend readings. However, it also means that recognising them takes longer. Using lower settings will result in more trends being detected earlier, but some of those trends can be false.

### Stochastic RSI

Stochastic RSI (StochRSI) is used to support stock market prediction by comparing a security’s price range and closing price. It is used to determine whether an asset is overbought (trading at a higher price than its inherent value) or oversold (trading at a lower price than its inherent value). The Stochastic RSI fluctuates between 0 and 1.</p>

By setting an overbought limit you confirm the minimum indicator value that can trigger a ‘sell’ signal, and by setting an oversold limit you confirm the maximum indicator value that can trigger a ‘buy’ signal. The most common settings are 0.8 and 0.2 accordingly.
The most common time periods setting used for the Stochastic RSI is 14. The number of periods can be adjusted up or down to identify longer-term or shorter-term trends.
Smooth 1 sets the window size for the moving average of Stochastic RSI, and Smooth 2 sets the window size for the moving average of %K (fast stochastic indicator). These moving averages help smooth price fluctuations.

### MACD

Moving average convergence divergence (MACD) is a trend-following momentum indicator that shows the relationship between two moving averages of a stock price. The MACD is calculated by subtracting the longer-period (slow) exponential moving average (EMA) from the shorter-period (fast) EMA.
The MACD crossing above the zero line, from below, triggers a ‘buy’ signal, and it crossing below the zero line triggers a ‘sell’ signal. The higher/lower the MACD line is from the zero, the stronger the signal and the likelihood of price moving significantly higher/lower.

The common MACD is the difference between a 26-day and a 12-day exponential moving average. By default, the MACD employs a smoothing factor in an exponential moving average, and the traditional setting for it is 9 periods.</p>


## How to use StockScreener

### Search page
 - Enter the ticker for your chosen stock in the search box.
 - Tick the boxes for the signals you would like to combine for the stock performance analysis and update the default parameters for these signals if required.
 - Click "Get Results" to run stock performance analysis using the selected signals/settings.</li>
 - If you are logged in, the results page will allow you to add the selected stock to your watchlist and/or save your combination of signals/settings so that it can be applied to your watchlisted items.

### Watchlist page
*Available to logged in users only*

- Make sure you have added at least one stock to your watchlist and saved your preferred combination of signals.
- Go to the "Watchlist" page to view today's performance analysis and recommendations for your watchlisted stocks based on the combination of signals you have previously saved.
- Click on the "Graph" button for the stock you are interested in to open the relevant graph(s) in a new tab.
- Click on the "Notes" button for a watchlisted stock to add/edit notes.
- Click on the "X" button to remove a stock from your watchlist.

### Back Tester page

- Select the combination of signals you would like to back test by ticking the relevant boxes and adjusting the default parameters if required.
- Tick the boxes for the additional back test parameters if required and adjust the default settings.   </li>
- Select the tickers for the stocks you would like to use for your back test. If you are logged in, all of your watchlisted stocks are available for a back test. If you are logged out or do not have any watchlisted stocks, you can select all or some of the suggested stocks listed. This is for demonstration purposes only, and we recommend that you register and run the back test for the stocks you are interested in.
- Click on the "Get Results" button to run the back test.
- If you like the outcome of the back test and wish to apply the selected signal settings to your watchlist, click "Save this signal" or "Replace saved signal" if you have previously saved a different custom signal.
