from AutoLogin import GoogleBardAutoLogin, MicrosoftBingAutoLogin
from dotenv import load_dotenv
import os
from time import sleep
import unittest

load_dotenv('../.env')
google_account = os.getenv('google_account')
google_password = os.getenv('google_password')
bing_account = os.getenv('bing_account')
bing_password = os.getenv('bing_password')
chrome_version = int(os.getenv('chrome_version'))

# python -m unittest AutoLoginTest.GoogleBardTest
class GoogleBardTest(unittest.TestCase):
    def test_find_sign_in_button(self):
        print('\n==== Testing for find_sign_in_button() ====')
        auto_login = GoogleBardAutoLogin(google_account, google_password, chrome_version)
        sign_in_button = auto_login.find_sign_in_button()
        self.assertEqual(sign_in_button.tag_name, 'span')
        self.assertNotEqual(sign_in_button.get_attribute('class'), None)
        self.assertEqual(sign_in_button.text.strip(), 'Sign in')
        #sleep(100)
        auto_login.driver.close()

    def test_find_account_input(self):
        print('\n==== Testing for find_account_input() ====')
        auto_login = GoogleBardAutoLogin(google_account, google_password, chrome_version)
        account_input = auto_login.find_account_input()
        self.assertEqual(account_input.tag_name, 'input')
        self.assertEqual(account_input.get_attribute('type'), 'email')
        self.assertNotEqual(account_input.get_attribute('class'), None)
        self.assertEqual(account_input.get_attribute('aria-label'), 'Email or phone')
        self.assertEqual(account_input.get_attribute('name'), 'identifier')
        #sleep(100)
        auto_login.driver.close()

    def test_find_password_input(self):
        print('\n==== Testing for find_password_input() ====')
        auto_login = GoogleBardAutoLogin(google_account, google_password, chrome_version)
        password_input = auto_login.find_password_input()
        if password_input != None:
            self.assertEqual(password_input.tag_name, 'input')
            self.assertEqual(password_input.get_attribute('type'), 'password')
            self.assertNotEqual(password_input.get_attribute('class'), None)
            self.assertEqual(password_input.get_attribute('aria-label'), 'Enter your password')
            self.assertEqual(password_input.get_attribute('name'), 'Passwd')
        #sleep(100)
        auto_login.driver.close()

    def test_get_cookie_list(self):
        print('\n==== Testing for get_cookie_list() ====')
        auto_login = GoogleBardAutoLogin(google_account, google_password, chrome_version)
        cookie_list = auto_login.get_cookie_list()
        if cookie_list != None:
            self.assertIsInstance(cookie_list, list)
            exist_name = False
            for cookie_dict in cookie_list:
                self.assertIsInstance(cookie_dict, dict)
                self.assertIn('domain', cookie_dict)
                self.assertIsInstance(cookie_dict['domain'], str)
                self.assertNotEqual(cookie_dict['domain'], '')
                self.assertIn('expiry', cookie_dict)
                self.assertIsInstance(cookie_dict['expiry'], int)
                self.assertGreaterEqual(cookie_dict['expiry'], 0)
                self.assertIn('name', cookie_dict)
                self.assertIsInstance(cookie_dict['name'], str)
                self.assertNotEqual(cookie_dict['name'], '')
                self.assertIn('value', cookie_dict)
                self.assertIsInstance(cookie_dict['value'], str)
                self.assertNotEqual(cookie_dict['value'], '')
                if cookie_dict['name'] == '__Secure-1PSID':
                    exist_name = True
            self.assertEqual(exist_name, True)
        #sleep(100)
        auto_login.driver.close()

    def test_get_cookie(self):
        print('\n==== Testing for get_cookie() ====')
        auto_login = GoogleBardAutoLogin(google_account, google_password, chrome_version)
        cookie = auto_login.get_cookie()
        if cookie != None:
            self.assertIsInstance(cookie, str)
            self.assertNotEqual(cookie, '')
        #sleep(100)
        auto_login.driver.close()

# python -m unittest AutoLoginTest.MicrosoftBingAutoLoginTest
class MicrosoftBingAutoLoginTest(unittest.TestCase):
    def test_find_account_input(self):
        print('\n==== Testing for find_account_input() ====')
        auto_login = MicrosoftBingAutoLogin(bing_account, bing_password, chrome_version)
        account_input = auto_login.find_account_input()
        self.assertEqual(account_input.tag_name, 'input')
        self.assertEqual(account_input.get_attribute('type'), 'email')
        self.assertEqual(account_input.get_attribute('name'), 'loginfmt')
        self.assertNotEqual(account_input.get_attribute('id'), None)
        self.assertNotEqual(account_input.get_attribute('class'), None)
        self.assertNotEqual(account_input.get_attribute('aria-label'), None)
        self.assertNotEqual(account_input.get_attribute('placeholder'), None)
        #sleep(100)
        auto_login.driver.close()

    def test_find_password_input(self):
        print('\n==== Testing for find_password_input() ====')
        auto_login = MicrosoftBingAutoLogin(bing_account, bing_password, chrome_version)
        password_input = auto_login.find_password_input()
        self.assertEqual(password_input.tag_name, 'input')
        self.assertEqual(password_input.get_attribute('name'), 'passwd')
        self.assertNotEqual(password_input.get_attribute('id'), None)
        self.assertNotEqual(password_input.get_attribute('class'), None)
        self.assertNotEqual(password_input.get_attribute('placeholder'), None)
        self.assertNotEqual(password_input.get_attribute('aria-label'), None)
        #sleep(100)
        auto_login.driver.close()

    def test_get_cookies(self):
        print('\n==== Testing for test_get_cookies() ====')
        auto_login = MicrosoftBingAutoLogin(bing_account, bing_password, chrome_version)
        cookies = auto_login.get_cookies()
        self.assertIsInstance(cookies, list)
        for cookie_dict in cookies:
            self.assertIsInstance(cookie_dict, dict)
            self.assertIn('domain', cookie_dict)
            self.assertIsInstance(cookie_dict['domain'], str)
            self.assertNotEqual(cookie_dict['domain'], '')
            self.assertIn('name', cookie_dict)
            self.assertIsInstance(cookie_dict['name'], str)
            self.assertNotEqual(cookie_dict['name'], '')
            self.assertIn('value', cookie_dict)
            self.assertIsInstance(cookie_dict['value'], str)
            self.assertNotEqual(cookie_dict['value'], '')
        #sleep(100)
        auto_login.driver.close()

    def test_dump_cookies(self):
        print('\n==== Testing for test_dump_cookies() ====')
        auto_login = MicrosoftBingAutoLogin(bing_account, bing_password, chrome_version)
        auto_login.dump_cookies()
        self.assertEqual(os.path.exists('cookies.json'), True)
        #sleep(100)
        auto_login.driver.close()