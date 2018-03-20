#!/usr/bin/python3

try:
    import time
    import json
    import argparse
    from converters import ConverterXE, ConverterOER, ConversionError
except ModuleNotFoundError:
    print('Required modules could not be imported. '
          'Please install packages by running: "pip install -r requirements.txt"')
    exit(1)


class ArgParser(argparse.ArgumentParser):
    """Class for validating and parsing of command line arguments."""
    def __init__(self):
        super().__init__()
        self.add_argument('--amount', '-a',
                          help='amount to convert: <number>')
        self.add_argument('--input_currency', '-i',
                          help='currency to convert from: <currency code or symbol>')
        self.add_argument('--output_currency', '-o',
                          help='currency to convert to: <currency code or symbol>')
        self.add_argument('--converter', '-c',
                          help='override the conversion method: <"xe" or "oer">')
        self.add_argument('--currencies', action='store_true',
                          help='print a list of currencies, no conversion is done')

    def parse(self):
        """Validate command line arguments and parse them for further use.

        ArgParser reflects the two ways to use the application from CLI.

        If the program is run with the "currencies" option, other parameters
        are ignored and the function returns True for "list_currs" option.

        If "currencies" option is not used, "amount" and "input_currency"
        parameters become required. If any of them is missing or if "amount"
        is not a number, the program quits with a reference to the README.

        Options and required parameters are parsed and returned as a list.
        """
        args = self.parse_args()

        # Check if the "--currencies" option is used.
        # If so, skip parsing of other args, since they are not used.
        list_currs = args.currencies
        if list_currs:
            return [None, '', list_currs]

        # Validate and parse remaining CLI args.
        params = dict()

        if args.amount:
            try:
                params['amount'] = float(args.amount)
            except ValueError:
                print('Given "--amount" argument is not a valid number. '
                      'Refer to README to see the usage.')
                exit(1)
        else:
            print('Missing "--amount" argument. '
                  'Refer to README to see the usage.')
            exit(1)

        if args.input_currency:
            params['in_currency'] = args.input_currency.upper()
        else:
            print('Missing "--input_currency" argument. '
                  'Refer to README to see the usage.')
            exit(1)

        try:
            params['out_currency'] = args.output_currency.upper()
        except AttributeError:
            params['out_currency'] = None

        try:
            override_converter = args.converter.lower()
        except AttributeError:
            override_converter = ''

        return [params, override_converter, list_currs]


class App:
    """Main class leading the individual steps in the program execution."""
    def __init__(self, params, override_converter, list_currs):
        self.config = self.load_config()
        self.converter = self.set_converter(override_converter)
        self.list_currs = list_currs

        # Set conversion parameters only if "--currencies" option is not selected.
        if self.list_currs is not True:
            self.params = {
                'amount': params['amount'],
                'in_currency': self.check_currency(params['in_currency'], 'in'),
                'out_currency': self.check_currency(params['out_currency'], 'out')
            }
            self.out_currs = self.params['out_currency']

    def load_config(self):
        """Load configuration from a file."""
        with open('config.json', 'r') as f:
            return json.load(f)

    def set_converter(self, override_converter):
        """Set the conversion method and return a converter object.

        Creates one of two possible converter objects depending on
        an optional overriding argument or the config file, whereas
        the overriding argument has a priority. The converter object
        is created with settings from the config file.
        """
        if 'xe' in override_converter:
            return ConverterXE(self.config['verbosity'],
                               self.config['currencies_expiration'])
        elif 'oer' in override_converter:
            return ConverterOER(self.config['oer_config'],
                                self.config['verbosity'],
                                self.config['currencies_expiration'])
        else:
            if self.config['converter'] == 'ConverterXE':
                return ConverterXE(self.config['verbosity'],
                                   self.config['currencies_expiration'])
            else:
                return ConverterOER(self.config['oer_config'],
                                    self.config['verbosity'],
                                    self.config['currencies_expiration'])

    def check_currency(self, string, which):
        """Check if a given string is a valid currency code or symbol.

        Argument "which" determines if the tested currency is input or
        output. If it is the input currency and it fails the test,
        an error is raised that is handled in function main().
        """
        if string is None:
            return None

        # Check if the string is a valid code.
        if string in self.converter.currencies:
            return string

        # Check if the string is a valid symbol and convert it to a code.
        for code, values in self.converter.currencies.items():
            if "'symbol': '{}'".format(string) in str(values):
                return code

        # The string is invalid.
        if which == 'out':
            self.vprint('The entered output currency is invalid, '
                        'amount will be converted to all currencies.')
            return None
        elif which == 'in':
            raise ValueError

    def run(self):
        """Run the main part of the App class and return the output.

        If the "currencies" option is enabled, don't do any conversion,
        only return a list of currency information. Distinguish between
        running from the CLI and calling from the web app. The first
        case returns a string ready to be printed to the console,
        while the other case returns a list of dictionaries.

        Without the "currencies" option, build a dictionary for
        the output, utilizing the get_conversion() helper function.
        The output dictionary is also logged to the log file.
        """
        if self.list_currs:
            curr_list = self.converter.list_currencies()

            if __name__ == '__main__':
                list_print = '\n{}{}{}\n'.\
                    format('Code'.ljust(7, ' '), 'Symbol'.ljust(8, ' '), 'Name')
                for curr in curr_list:
                    list_print = list_print + '{}{}{}\n'.format(
                        curr['code'].ljust(7, ' '),
                        curr['symbol'].ljust(8, ' '),
                        curr['name']
                    )
                return list_print
            else:
                return curr_list

        else:
            output = {
                'input': {
                    'amount': self.params['amount'],
                    'currency': self.params['in_currency']
                },
                'output': self.get_conversion()
            }
            self.log(output)
            return output

    def get_conversion(self):
        """Build and return a dictionary of converted values.

        Firstly, determine what output currencies should be used.
        If there is a valid given output currency, use that one.
        Otherwise use a setting in the config file to decide,
        whether all known currencies should be used or there is
        an overriding list.

        Then loop over all the chosen output currencies and
        convert them. If an ConversionError occurs, it might be
        caused by an unsupported currency, in which case continue
        with the loop.

        If there is another type of ConversionError, caused e.g.
        by lack of internet connection or the external service
        outage, raise an exception handled in function main().
        """
        self.vprint(f'Using {self.converter.name} conversion method.')

        if self.out_currs is not None:
            self.out_currs = [self.out_currs]
        else:
            if self.config['override_currencies'] is False:
                self.out_currs = self.converter.currencies
            else:
                self.out_currs = self.config['override_currencies']

        converted = dict()
        for curr in self.out_currs:
            if curr == self.params['in_currency']:
                converted[curr] = self.params['amount']
            else:
                try:
                    converted[curr] = self.converter.convert({
                        'amount': self.params['amount'],
                        'in_currency': self.params['in_currency'],
                        'out_currency': curr
                    })
                except ConversionError as error:
                    if error.type == 'unsupported':
                        continue
                    else:
                        raise
                else:
                    converted[curr] = round(converted[curr], 2)
        return converted

    def vprint(self, *a, **k):
        """Print detailed information if verbosity is enabled."""
        print(*a, **k) if self.config['verbosity'] else None

    def log(self, record):
        """Save the executed conversion to the log file, if enabled."""
        if self.config['log_filename'] is not False:
            with open(self.config['log_filename'], 'a') as f:
                f.write(f'{time.time()}: {record}\n')


def main(CLI=True, params=None, override_converter='', list_currs=False,
         first_try=True):
    """Get parameters for the program and execute it.

    When the program is run from the CLI, the parameters are parsed
    from the CLI arguments. Otherwise the parameters should be passed
    as function arguments.

    Create an App object and its converter object. Handle various
    exceptions that may occur in the process.

    Call the App's run() method to get the output of the App. If an
    error occurs during the conversion, try one more time with the
    other conversion method by recursively calling function itself.

    If running of the App is successful, print the output to the
    console and return it to the caller (e.g. a web app).
    """
    if CLI:
        parser = ArgParser()
        params, override_converter, list_currs = parser.parse()

    try:
        app = App(params, override_converter, list_currs)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        print('ERROR: Configuration file "config.json" is missing or corrupted.')
        return [2, 'Configuration file is missing or corrupted.']
    except ValueError:
        print('ERROR: Given input currency is not a valid currency code or symbol.')
        return [1, 'Given input currency is not a valid currency code or symbol.']
    except ConversionError:
        print('ERROR: No currencies data available. Program terminating.')
        return [2, 'No currencies data available.']

    try:
        output = app.run()
    except ConversionError as error:
        if first_try is False:
            print('ERROR: Both conversion methods failed. '
                  'Check your internet connection.')
            return [2, 'Conversion failed.']
        if error.type == 'xe_error':
            print('ERROR: XE conversion method failed. Retrying with OER method.\n')
            output = main(CLI=False, params=params, override_converter='oer',
                          first_try=False)
        if error.type == 'oer_error':
            print('ERROR: OER conversion method failed. Retrying with XE method.\n')
            output = main(CLI=False, params=params, override_converter='xe',
                          first_try=False)
    else:
        if not list_currs:
            output = json.dumps(output, indent=4)
        print(output)

    return [0, output]


if __name__ == '__main__':
    main(CLI=True)
