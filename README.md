## Currency converter: *a CLI & web app*
### Description:

This simple Python program serves as a utility to quickly and reliably convert values from one currency to another, or to multiple other currencies. The program can be used through two different APIs: a command line interface or a web application.

For the conversion itself, the program takes two required arguments - amount to be converted and the input currency to convert from. The output currency may or may not be given. If the output currency is provided, the program only converts the amount to the given currency. Otherwise it converts the amount to all enabled currencies.

The currency arguments should preferably be entered in form of [ISO 4217 currency codes](https://en.wikipedia.org/wiki/ISO_4217). Currency symbols are supported as well, however they come with a caveat. There is no official unifying ISO standard in case of currency symbols, therefore these can be ambiguous. The dollar sign ($) represents multiple currencies apart from the US dollar, including e.g. Australian or Canadian dollar. The list of supported symbols is thus limited in order to primarily represent the most widespread currencies. The complete list of supported currency names, codes and symbols can be accessed via both the CLI and web API (usage explained below).


### Conversion methods:

The program uses two different methods for the currency conversion. One of them depends on the [API endpoint of openexchangerates.org](https://docs.openexchangerates.org/docs/latest-json) ("OER"), which provides hourly-updated exchange rates. This app uses a free plan at openexchangerates.org, which allows 1,000 requests per month. This limit is addressed by caching the rates data into a local file, meaning that the program is sending requests to the OER endpoint only once in an hour and then gets the rates data from the local cache.

The other method of conversion is utilizing [http://www.xe.com/currencyconverter/](http://www.xe.com/currencyconverter/) website ("XE"), which accepts url arguments and returns an html page with the calculated conversion. This html page is then scraped and the converted amount is extracted. This method requires sending an HTTP request for every single conversion and may take long time (approx. 3 minutes) if the conversion is to be made for all known currencies. Therefore, this method is deprecated for converting to all currencies and should only be used with overridden currencies in the config file (configuration explained in the following section) or with a given output currency. The XE method could be significantly faster with asyncio and aiohttp, which might be implemented in future versions.

Of these two methods, the OER is much faster, especially when using the cache, and it also supports more currencies. For these reasons, the OER method is used as default all the time, unless overridden in the config file or by a command line argument. The XE method serves mainly as a backup for OER in case of outages or other unexpected events. If any of the attempted methods fails, the program automatically attempts to do the conversion once again using the other method.

The two methods were implemented also for the sake of demonstrating different approaches to currency conversion: requesting the conversion itself vs. requesting the exchange rates and doing the calculation locally.


### Additional features:

**Caching** - two kinds of data make use of caching: currencies list for both converters, and exchange rates list for the OER converter. The expiration time for both of these caches can be set in the config file.

**Logging** - every successful conversion (via both CLI and web API) is logged into a file for usage statistics gathering.

**Configuration** - the config.json file is part of the repository and contains key-value pairs of settings for the application. The config keys are as follows:
* override_currencies - enter a list of selected currencies (e.g. `["EUR", "USD"]`) or `false` to use all known currencies (default: `false`)
* currencies_expiration - enter time in minutes after which the currencies data is invalidated and has to be requested again (default: `1440`, which equals to 1 day)
* converter - enter the conversion method to be used (default: `"ConverterOER"`)
* verbosity - enter true/false to enable/disable detailed verbose messages during the execution of program in CLI (default: `false`)
* log_filename - enter the name of a file to log the usage history to or false to disable the logging (default: `"history.json"`)
* oer_config.app_id - enter the app_id to be used with HTTP requests to OER endpoint, required by OER
* oer_config.rates_expiration - enter time in minutes after which the exchange rates data is invalidated and has to be requested again (default: `60`)


### Requirements:

In order to run the program, Python 3 is required. Python 3.6 or higher is recommended.

It's also recommended to create an isolated virtual environment for the program. If needed, please refer to the [venv tutorial](https://docs.python.org/3/tutorial/venv.html).

Once the virtual environment is created, copy the repository files into the virtual environment directory. Then activate the virtual environment and install required packages and dependencies by running:
```
python3 -m pip install -r requirements.txt
```


### CLI usage:

The program supports several command line arguments, their overview can be found below as well as by running `currency_converter.py --help`.

If the program is run with the "--currencies" option, all other arguments are ignored, the program doesn't do any conversion and only returns the list of all supported currency names, codes and symbols.

Without the "--currencies" option, two arguments are required: amount to be converted and the input currency to convert from. The output currency is optional and if it is provided, the program only converts the amount to the given currency. Otherwise it converts the amount to all enabled currencies.

```
usage: currency_converter.py [-h] [--amount AMOUNT]
                             [--input_currency INPUT_CURRENCY]
                             [--output_currency OUTPUT_CURRENCY]
                             [--converter CONVERTER] [--currencies]

optional arguments:
  -h, --help                                                show this help message and exit
  --amount AMOUNT, -a AMOUNT                                amount to convert: <number>
  --input_currency INPUT_CURRENCY, -i INPUT_CURRENCY        currency to convert from: <currency code or symbol>
  --output_currency OUTPUT_CURRENCY, -o OUTPUT_CURRENCY     currency to convert to: <currency code or symbol>
  --converter CONVERTER, -c CONVERTER                       override the conversion method: <"xe" or "oer">
  --currencies                                              print a list of currencies, no conversion is done
```

#### Examples:

```
$ ./currency_converter.py --amount 100 --input_currency usd --output_currency eur
$ ./currency_converter.py --amount 3.66 --input_currency AUD --output_currency ¥
$ ./currency_converter.py --amount 1000 --input_currency ₹ --output_currency $ --converter xe
$ ./currency_converter.py --amount 250 --input_currency czk
$ ./currency_converter.py --currencies
```


### Web API usage:
The web application is built on the Flask framework and offers two ways to interact with it. Firstly, you can use the `/` or `/currency_converter/` API endpoint to send GET requests for the conversion. Conversion parameters can be entered in the url after the endpoint in the following form:
```
?amount=<>&input_currency=<>&output_currency=<>&converter=<>
```
The parameters follow the same rules as in the CLI usage, hence the "output_currency" and "converter" are optional arguments. If the conversion is successful, this endpoint responds with json-formatted data.

#### Examples:

```
GET /currency_converter?amount=3000&input_currency=CZK&output_currency=usd HTTP/1.1
GET /currency_converter?amount=150&input_currency=$&output_currency=EUR HTTP/1.1
GET /currency_converter?amount=10&input_currency=CA$&output_currency=A$&converter=xe HTTP/1.1
GET /currency_converter?amount=541.40&input_currency=€ HTTP/1.1
```

The other way to use the web application is to open an endpoint in the browser. Currently supported endpoints are following:
`/about/` contains some basic information about the project
`/currencies/` shows the list of supported currencies, their codes and symbols (equivalent to the "--currencies" option in the CLI usage)
`/converter/` contains a form for user-friendly input of conversion parameters and returns the conversion in html format
`/` and `/currency_converter/` redirect to the "converter" endpoint if no arguments are entered in the url

Please note that the interactive HTML version of the web application is in an early stage and should be considered a working prototype, not a final website. It can be deployed from the source or visited at this location: http://currency-converter.ddns.net
