# csc_webhook

A Discord Webhook used to display the current status of the Waterloo Computer Science Club office.

The source of info for the office status is: https://csclub.uwaterloo.ca/~n3parikh/office-status.json


## Install

Prerequisites: `python 3.10`

```bash
git clone https://github.com/hydrobeam/csc_webhook
cd csc_webhook
python3 -m venv /path/to/venv
```

[Activate](https://docs.python.org/3/tutorial/venv.html#creating-virtual-environments) the virtual environment, then:

``` bash
python3 -m pip install -r requirements.txt
```


## Running

First, modify the default `config.ini` file with the desired webhook URL.

Then, to run the script:

``` bash
python3 csc_webhook.py
```


