import random

from django.test import Client, TestCase, LiveServerTestCase
from django.urls import reverse
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager

from .models import User, SavedSearch, SignalConstructor


# Testing using TestCase

class GeneralTest(TestCase):
    def setUp(self):
        # Create new users
        userA = User.objects.create(username="AAA", email="usera@user.user", password="abcdefg")
        userB = User.objects.create(username="BBB", email="userb@user.user", password="hijklmn")

        # Create signals for each user
        SignalConstructor.objects.create(user=userA, psar=True, psarAF=0.02, psarMA=0.2, adx=True, adxW=18, adxL=20)
        SignalConstructor.objects.create(user=userB, ma=True)

        # Save instruments for each user
        SavedSearch.objects.create(user=userA, ticker='AAPL', ticker_full='Apple Inc.')
        SavedSearch.objects.create(user=userA, ticker='MRNA', ticker_full='Moderna, Inc.')
        SavedSearch.objects.create(user=userB, ticker='SBUX', ticker_full='Starbucks Corporation')

    def test_user_signal_count(self):
        a = User.objects.get(username="AAA")
        self.assertEqual(a.savedSignal.all().count(), 1)
        b = User.objects.get(username="BBB")
        self.assertEqual(b.savedSignal.all().count(), 1)

    def test_saved_searches(self):
        a = User.objects.get(username="AAA")
        b = User.objects.get(username="BBB")
        self.assertEqual(len(a.watchlist.all()), 2)
        self.assertEqual(len(b.watchlist.all()), 1)

    def test_index(self):
        c = Client()
        response = c.get("/")
        self.assertEqual(response.status_code, 200)

    def test_login(self):
        c = Client()
        c.login(username='AAA', password='abcdefg')
        response = c.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_watchlist(self):
        a = User.objects.get(username="AAA")
        self.client.force_login(user=a)
        response = self.client.get(reverse('watchlist'))
        self.assertEqual(len(response.context["watched_tickers"]), 2)
        self.assertNotEqual(response.context['htmlResultTable'], None)
        self.assertEqual(response.status_code, 200)

    def test_backtest(self):
        b = User.objects.get(username="BBB")
        self.client.force_login(user=b)
        response = self.client.get(reverse('backtester'))
        self.assertEqual(response.status_code, 200)


class SeleniumTest(LiveServerTestCase):
    signals = ['ma', 'psar', 'adx', 'srsi', 'macd']
    # test with min 2 signals to avoid testing with ADX alone
    num_of_signals = range(2, (len(signals) + 1))
    username = "tester"
    email = "tester@tester.tester"
    password = "tester"
    confirmation = "tester"

    def setUp(self):
        self.driver = webdriver.Chrome(ChromeDriverManager().install())
        self.driver.get(self.live_server_url)
        login_link = self.driver.find_element_by_link_text("Register")
        self.driver.execute_script("arguments[0].click();", login_link)

        username_el = self.driver.find_element_by_name("username")
        username_el.send_keys(self.username)
        email_el = self.driver.find_element_by_name("email")
        email_el.send_keys(self.email)
        password_el = self.driver.find_element_by_name("password")
        password_el.send_keys(self.password)
        confirmation_el = self.driver.find_element_by_name("confirmation")
        confirmation_el.send_keys(self.password)

        self.driver.find_element_by_css_selector("form").submit()

    def test_all(self):

        # search page
        search_link = self.driver.find_element_by_link_text("Search")
        self.driver.execute_script("arguments[0].click();", search_link)
        self.driver.find_element_by_id('id_ticker').send_keys("AAPL")
        element = self.driver.find_element_by_id('searchButton')
        self.driver.execute_script("arguments[0].click();", element)
        resultTable = self.driver.find_element_by_class_name('stock_table')
        graph = self.driver.find_element_by_class_name('plotly-graph-div')
        assert resultTable is not None
        assert graph is not None
        add_link = self.driver.find_element_by_class_name('watchlist')
        self.driver.execute_script("arguments[0].click();", add_link)


        #search_with_signals:

        for n in self.num_of_signals:
            search_link = self.driver.find_element_by_link_text("Search")
            self.driver.execute_script("arguments[0].click();", search_link)

            self.driver.find_element_by_id('id_ticker').send_keys("GS")
            selected_signals = random.sample(self.signals, k=n)
            for s in selected_signals:
                s_element = self.driver.find_element_by_id(f"id_{s}")
                if not s_element.is_selected():
                    self.driver.execute_script("arguments[0].click();", s_element)

            element = self.driver.find_element_by_id('searchButton')
            self.driver.execute_script("arguments[0].click();", element)
            resultTable = self.driver.find_element_by_class_name('stock_table')
            graph = self.driver.find_element_by_class_name('plotly-graph-div')
            assert resultTable is not None
            assert graph is not None

       # backtest_with_signals:

        for n in self.num_of_signals:
            backtest_link = self.driver.find_element_by_link_text("Back Tester")
            self.driver.execute_script("arguments[0].click();", backtest_link)

            selected_signals = random.sample(self.signals, k=n)

            for s in selected_signals:
                s_element = self.driver.find_element_by_id(f"id_{s}")
                if not s_element.is_selected():
                    self.driver.execute_script("arguments[0].click();", s_element)

            element = self.driver.find_element_by_id('searchButton')
            self.driver.execute_script("arguments[0].click();", element)
            resultTable = self.driver.find_element_by_id('outcome_card')

            assert resultTable is not None


    def tearDown(self):
        self.driver.quit
