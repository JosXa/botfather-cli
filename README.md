# botfather-cli
A Command Line Interface for Telegram BotFather

## Installation

1. python3 setup.py install
2. This utility uses [TgIntegration](https://github.com/JosXa/tgintegration/) (and thus [Pyrogram](https://github.com/pyrogram/pyrogram)). Create a file `.botfather` in your home directory with the following contents:
```
[pyrogram]
api_id=...
api_hash=...
```
Replace the ellipses (`...`) with appropriate values as described in [Telegram API Keys](https://docs.pyrogram.ml/start/Setup#api-keys).

## Usage

```
$ botfather --help
Usage: botfather [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  deletebot
  newbot
  revoke
  setabouttext
  setcommands
  setdescription
  setname
  switch
  token

```

## Multiple Telegram Accounts

Using `$ botfather switch`, you can make use of multiple Telegram sessions, so that you can spread your bots across multiple accounts and circumvent the 20 bots per account limit.
