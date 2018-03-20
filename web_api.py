#!/usr/bin/python3

try:
    import json
    from flask import Flask, request, redirect, url_for, render_template
    from flask_wtf import Form
    from wtforms import StringField, DecimalField
    from wtforms.validators import DataRequired
    import currency_converter
except ModuleNotFoundError:
    print('Required modules could not be imported. '
          'Please install packages by running: "pip install -r requirements.txt"')
    exit(1)


class ConverterForm(Form):
    """"Form class used in the "/converter" route."""
    amount = DecimalField('Amount: ', validators=[DataRequired()])
    in_currency = StringField('From: ', validators=[DataRequired()])
    out_currency = StringField('To: ')


app = Flask(__name__)
app.config['SECRET_KEY'] = 'r4=sVI57i\>lEsp0-b04b.iD@?8>v_'


@app.route('/', methods=['GET'])
@app.route('/currency_converter', methods=['GET'])
def convert():
    """Handle routes for a direct conversion and return output.

    If the two defined routes are used without any argument, they
    redirect to the interactive form web page.

    If arguments are given, check them and return an error message,
    if arguments are not valid. Otherwise call the main app and get
    its output.

    If the conversion is successful, return the conversion data in
    json format. Otherwise return an error message and error code
    for the client-side or server-side error.
    """
    if len(request.args) == 0:
        return redirect(url_for('convert_form'))

    params = dict()

    try:
        params['amount'] = float(request.args.get('amount'))
    except TypeError:
        return 'Request Error: Missing required argument: "amount".', 400
    except ValueError:
        return 'Request Error: Given amount is not a valid number.', 400

    try:
        params['in_currency'] = request.args.get('input_currency').upper()
    except AttributeError:
        return 'Request Error: Missing required argument: "input_currency".', 400

    try:
        params['out_currency'] = request.args.get('output_currency').upper()
    except AttributeError:
        params['out_currency'] = None

    try:
        override_converter = request.args.get('converter').lower()
    except AttributeError:
        override_converter = ''

    output = currency_converter.main(
        CLI=False, params=params, override_converter=override_converter)

    if output[0] == 0:
        return output[1], 200, {'Content-Type': 'application/json; charset=utf-8'}
    elif output[0] == 1:
        message = 'Request Error: ' + output[1]
        return message, 400
    elif output[0] == 2:
        message = 'Internal Server Error: ' + output[1]
        return message, 500


@app.route('/about', methods=['GET'])
def about():
    """Return the "about.html" template."""
    return render_template('about.html')


@app.route('/currencies', methods=['GET'])
def list_currencies():
    """Get the currencies data and render them in template."""
    output = currency_converter.main(CLI=False, list_currs=True)
    currencies = output[1]
    return render_template('currencies.html', currencies=currencies)


@app.route('/converter', methods=['GET', 'POST'])
def convert_form():
    """Handle the interactive conversion form route.

    If the route is requested by GET method, return an empty
    conversion form template. When the form is submitted,
    test the validity of the given parameters and render an
    error message, if any.

    If the conversion by the main app is successful, render
    the form template with the converted data.
    """
    form = ConverterForm()
    params = dict()

    if request.method == 'POST':
        if form.validate():
            params['amount'] = float(request.form['amount'])
            params['in_currency'] = request.form['in_currency'].upper()
            params['out_currency'] = request.form['out_currency'].upper()

            output = currency_converter.main(
                CLI=False, params=params, override_converter='')

            if output[0] == 0:
                converted = json.loads(output[1])
                return render_template('converter.html',
                                       form=form, converted=converted)
            else:
                message = output[1]

        else:
            message = 'Please enter a valid amount and input currency.'

        return render_template('converter.html', form=form, message=message)

    return render_template('converter.html', form=form)


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
