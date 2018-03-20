#!/usr/bin/python3

try:
    import time
    import json
    import requests
    from bs4 import BeautifulSoup
except ModuleNotFoundError:
    print('Required modules could not be imported. '
          'Please install packages by running: "pip install -r requirements.txt"')
    exit(1)


class ConversionError(Exception):
    """Exception for errors during conversion."""
    def __init__(self, type):
        self.type = type


class ExpiredError(Exception):
    """Exception for expired cache."""
    pass


class ConverterCommon:
    """Parent class for both conversion methods."""
    def __init__(self, verbosity, curr_exp):
        self.url_currs = \
            'http://www.localeplanet.com/api/auto/currencymap.json?name=Y'
        self.filepath = '.' if __name__ == '__main__' else './converters'
        self.verbosity = verbosity
        self.curr_exp = float(curr_exp) * 60
        self.currencies = dict()
        self.load_currencies()

    def load_currencies(self):
        """Load currencies from local cache or from remote server.

        Firstly, check if currencies cache is available and not
        corrupted. Then test if it is not older than the expiration
        time. If successful, return the currencies from local cache.

        Otherwise call the get_currencies() method to get currencies
        from the remote server. If successful, save the currencies
        data to cache. If an error occurs during get_currencies(),
        use the expired local cache if available or exit the program
        if local cache is unusable.
        """
        missing = False

        try:
            with open(f'{self.filepath}/cache_currencies.json', 'r') as f:
                cache = json.load(f)
            time_diff = time.time() - cache['timestamp']
            if time_diff > self.curr_exp:
                raise ExpiredError
        except (FileNotFoundError, KeyError, TypeError, json.decoder.JSONDecodeError):
            self.vprint('Currencies data cache is missing or corrupted.')
            missing = True
        except ExpiredError:
            self.vprint('Currencies data cache is outdated.')
        else:
            self.currencies = cache['currencies']
            self.vprint('Using currencies data from cache.')
            return

        try:
            self.get_currencies()
        except Exception:
            if missing:
                raise ConversionError(type='no_currs_data')
            else:
                self.vprint('Using currencies data from cache, '
                            'despite being older than expiration time.')
                self.currencies = cache['currencies']
        else:
            self.save_currencies()
            self.vprint('Saving currencies data to cache.')

    def get_currencies(self):
        """Get currencies data from the remote server."""
        self.vprint(f'Getting currencies data from {self.url_currs}')
        try:
            response = requests.get(self.url_currs).json()
        except Exception:
            print('Error occurred while requesting currencies!')
            raise

        for key, value in response.items():
            self.currencies[key] = {
                'symbol': value['symbol'],
                'name': value['name']
            }

    def save_currencies(self):
        """Save currencies data to the local cache."""
        with open(f'{self.filepath}/cache_currencies.json', 'w') as f:
            cache = {
                'timestamp': time.time(),
                'currencies': self.currencies
            }
            f.write(json.dumps(cache))

    def list_currencies(self):
        """Return a list of dictionaries of currency data."""
        output = list()
        for code, curr in self.currencies.items():
            output.append({
                'code': code,
                'symbol': curr['symbol'],
                'name': curr['name']
            })
        return output

    def vprint(self, *a, **k):
        """Print detailed information if verbosity is enabled."""
        print(*a, **k) if self.verbosity else None


class ConverterXE(ConverterCommon):
    """Class for the XE conversion method."""
    def __init__(self, verbosity=False, curr_exp=1440):
        super().__init__(verbosity, curr_exp)
        self.name = 'XE'
        self.url_convert = 'http://www.xe.com/currencyconverter/convert/'
        self.params = {}

    def convert(self, params):
        """Execute the conversion with given parameters.

        Call the get_response() method to get the conversion
        from the remote server. If an error occurs, raise an
        error handled by the main app.

        If response is available, call the check_response()
        method to test if it is as expected. If the test passes,
        return the converted value. Otherwise, raise a non-fatal
        "unsupported" exception to the main app.
        """
        self.params = {
            'Amount': params['amount'],
            'From': params['in_currency'],
            'To': params['out_currency']
        }

        try:
            response = self.get_response()
        except Exception:
            raise ConversionError(type='xe_error')

        if self.check_response(response) is not False:
            return response['converted']
        else:
            self.vprint('Given input and/or output currency is not supported '
                        'by XE method and is skipped: '
                        '{} and/or {}'
                        .format(params['in_currency'], params['out_currency']))
            raise ConversionError(type='unsupported')

    def get_response(self):
        """Get response from the server and return the conversion."""
        response = requests.get(self.url_convert, params=self.params).content
        bs = BeautifulSoup(response, "lxml")
        converted = bs.find('span', class_='uccResultAmount').text.replace(',', '')
        converted = float(converted)
        returned_currs = [
            bs.find('span', class_='uccFromResultAmount').text[-5:-2],
            bs.find('span', class_='uccToCurrencyCode').text
            ]
        return {'converted': converted,
                'returned_currs': returned_currs}

    def check_response(self, response):
        """Check if the response from XE is as expected.

        The XE server checks if given currency codes are valid and if
        they are not, they are replaced with the default USD currency.

        Check if the response from XE contains such a replacement
        and if it does, consider the conversion unsuccessful.
        """
        if (response['returned_currs'][0] != self.params['From'])\
                or (response['returned_currs'][1] != self.params['To']):
            return False


class ConverterOER(ConverterCommon):
    """Class for the OER conversion method."""
    def __init__(self, config, verbosity=False, curr_exp=1440):
        super().__init__(verbosity, curr_exp)
        self.name = 'OER'
        self.url_rates = 'https://openexchangerates.org/api/latest.json'
        self.app_id = config['app_id']
        self.rates_exp = float(config['rates_expiration']) * 60
        self.rates = None

    def convert(self, params):
        """Execute the conversion with given parameters.

        The conversion is calculated locally using exchange rates
        from the OER API.

        The free plan of OER API doesn't allow exchange rates for
        currencies other than USD. If the conversion is to be made
        for USD, it can be done directly. However, if USD is neither
        input nor output currency, the function is run in two steps,
        calling itself recursively to finish the conversion.
        """
        if self.rates is None:
            self.load_rates()

        try:
            if params['in_currency'] == 'USD':
                result = params['amount'] * self.rates[params['out_currency']]
            elif params['out_currency'] == 'USD':
                result = params['amount'] / self.rates[params['in_currency']]
            else:
                result = self.convert(
                    {'amount': params['amount'] / self.rates[params['in_currency']],
                     'in_currency': 'USD',
                     'out_currency': params['out_currency']})
        except KeyError as error:
            self.vprint('Given currency is not supported by OER method and is skipped:'
                        f' {error.args[0]}')
            raise ConversionError(type='unsupported')

        return result

    def load_rates(self):
        """Load exchange rates from cache or from remote server.

        Firstly, check if rates cache is available and not corrupted.
        Then test if it is not older than the expiration time. If
        successful, use the rates from local cache.

        If the cache is unusable or expired, get the rates data
        from the OER API and save them to the cache. If the get
        request fails, raise an error handled by the main app.
        """
        try:
            with open(f'{self.filepath}/cache_rates.json', 'r') as f:
                cache = json.load(f)
            time_diff = time.time() - cache['timestamp']
            if time_diff > self.rates_exp:
                raise ExpiredError
        except (FileNotFoundError, KeyError, TypeError, json.decoder.JSONDecodeError):
            self.vprint('Exchange rates cache is missing or corrupted.')
        except ExpiredError:
            self.vprint('Exchange rates cache is outdated.')
        else:
            self.rates = cache['rates']
            self.vprint('Using exchange rates from cache.')
            return

        try:
            self.vprint(f'Requesting exchange rates from {self.url_rates}')
            response = requests.get(self.url_rates,
                                    params={'app_id': self.app_id}).json()
        except Exception:
            raise ConversionError(type='oer_error')
        else:
            self.vprint('Saving exchange rates to cache.')
            self.rates = response['rates']
            self.save_rates(response)

    def save_rates(self, response):
        """Save exchange rates data to the local cache."""
        with open(f'{self.filepath}/cache_rates.json', 'w') as f:
            cache = {
                'timestamp': response['timestamp'],
                'rates': response['rates']
            }
            f.write(json.dumps(cache))
