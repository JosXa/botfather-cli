#!/bin/python3
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Pattern

import click
from tgintegration import BotIntegrationClient, Response
from tgintegration.containers.keyboard import NoButtonFound

MAIN_SESSION_NAME = 'botfather-cli'
config_location = Path('~/.botfather').expanduser()
session_dir = Path('botfather-sessions').expanduser()
session_dir.mkdir(exist_ok=True)

# TODO
# class Session:
#     def __init__(self, path):
#         self.path = path


client = None


class BotFatherClient(BotIntegrationClient):

    def __init__(self, config_file="./config.ini", **kwargs: Any) -> Any:
        super().__init__(
            bot_under_test='@botfather',
            max_wait_response=3,
            config_file=config_file,
            **kwargs)


def create_client(session_path: str = MAIN_SESSION_NAME, phone_number=None, verbose=False):
    client = BotFatherClient(
        phone_number=phone_number,
        session_name=os.path.splitext(session_path)[0],
        config_file=str(config_location),
    )
    if verbose:
        click.echo(f"Loading config from {config_location}...")
    client.load_config()
    if verbose:
        click.echo("Starting client...")
    client.start()
    return client


class Context(object):
    def __init__(self):
        self.verbose = False
        self._client = None
        self.bot = None

    @property
    def client(self) -> BotIntegrationClient:
        if self._client is not None:
            return self._client
        self._client = create_client(verbose=self.verbose)
        return self._client

    @client.setter
    def client(self, value):
        self._client = value

    @client.deleter
    def client(self):
        self._client = None


def disconnect(context: Context, error=None, message=None):
    if message:
        click.echo(message)

    if error:
        click.echo(error)

    click.echo('Disconnecting...')
    context.client.stop()


pass_context = click.make_pass_decorator(Context, ensure=True)

cli = click.Group()


def _choose_item(choices, prompt, find=None, return_pattern=None):
    if return_pattern:
        return_pattern = re.compile(return_pattern)
    choices = [str(x) for x in choices]
    click.echo()
    while True:
        try:
            if not find:
                click.echo('\n'.join(f"({n}) {c}"
                                     for n, c in enumerate(choices)))
                click.echo()
                find = click.prompt(prompt)

            if return_pattern:
                if return_pattern.search(find):
                    return find

            if find == 'q':
                raise SystemExit
            elif find.isnumeric():
                return next(x for n, x in enumerate(choices) if n == int(find))
            else:
                return next(x for x
                            in choices
                            if x.lower() == find.lower())
        except (StopIteration, TypeError) as e:
            print(e)
            find = None


def choose_bot(context: Context, response: Response, find: str = None) -> Response:
    if context.bot is not None:
        return

    all_buttons = []

    if response.reply_keyboard:
        all_buttons = response.keyboard_buttons
    elif response.inline_keyboards:
        markups = [response.inline_keyboards[-1]]
        while True:
            try:
                res = markups[-1].press_button_await(r'»')
            except NoButtonFound:
                break
            if res.reply_keyboard:
                markups.append(res.reply_keyboard)
            elif res.inline_keyboards:
                markups.append(res.inline_keyboards[-1])

        for markup in markups:
            for row in markup.rows:
                for button in row:
                    caption = button
                    if hasattr(button, 'text'):
                        caption = button.text
                    if caption not in ('»', '«'):
                        all_buttons.append(button)

    while True:
        try:
            if not find:
                click.echo('\n'.join(f"({n}) {getattr(x, 'text', x)}"
                                     for n, x in enumerate(all_buttons)))
                click.echo()
                find = click.prompt("Select a bot")

            if find == 'q':
                disconnect(context, "Aborted")
            elif find.isnumeric():
                button = next(x for n, x in enumerate(all_buttons) if n == int(find))
                context.bot = getattr(button, 'text', button)
            else:
                button = next(x for x
                              in all_buttons
                              if (
                                      getattr(x, 'text', x).replace('@', '').lower()
                                      == find.replace('@', '').lower()
                              ))
                context.bot = getattr(button, 'text', button)

            click.echo()
            return context.client.send_message_await(context.bot)

        except (StopIteration, TypeError) as e:
            print(e)
            find = None


@cli.command()
@click.argument('file', type=click.File('w+'), default='commands.txt', )
@click.option('-e', '--edit', flag_value='edit', default=False,
              help="Edit the commands file before executing")
@pass_context
def setcommands(context: Context, edit: bool, file=None):
    contents = file.read()

    if contents in (None, ''):
        edit = True

    if edit:
        click.echo(f"Opening {file.name} in default editor. Please enter a list of commands...")
        click.edit(contents, filename=file.name)

    file.seek(0)
    contents = file.read()

    if context.verbose:
        click.echo("Sending /setcommands")

    res = context.client.send_command_await('/setcommands', num_expected=1)
    choose_bot(context, res)

    click.echo(f'Setting commands on {context.bot}:\n\n{contents}')
    confirm = click.confirm("Please confirm")

    if confirm:
        res = context.client.send_message_await(contents)
        click.echo(res)

    disconnect(context)


def save_session(context, overwrite=False):
    me = context.client.get_me()
    if me.username:
        new_name = me.username
    elif me.last_name:
        new_name = me.first_name + ' ' + me.last_name
    else:
        new_name = me.phone_number

    new_session = str(session_dir / (new_name + '.session'))

    if not overwrite:
        if os.path.exists(new_session):
            click.echo(f"Not overwriting session at {new_session}.")
            return new_session

    shutil.copy(context.client.session_name + '.session', new_session)
    click.echo(f"Saved session to {new_session}")
    return new_session


@cli.command()
@pass_context
def switch(context: Context):
    save_session(context)
    context.client.stop()

    phone_pattern = re.compile(r'[0-9 ]{5,}')
    new_session_or_phone = _choose_item(session_dir.iterdir(), "Choose session or enter phone number",
                                        return_pattern=phone_pattern)
    if new_session_or_phone and phone_pattern.search(new_session_or_phone):
        os.remove(MAIN_SESSION_NAME + '.session')
        context.client = create_client(MAIN_SESSION_NAME, phone_number=new_session_or_phone)
        new_session_or_phone = save_session(context)
    else:
        context.client = create_client(new_session_or_phone)
        new_session_or_phone = save_session(context)
        shutil.copy(new_session_or_phone, MAIN_SESSION_NAME + '.session')
    click.echo(f"Switched to {new_session_or_phone}.")
    disconnect(context)


def init_command(context: Context, command, find_bot=None):
    if not command.startswith('/'):
        command = '/' + command

    res = context.client.send_command_await(command, num_expected=1)
    if 'Choose a bot' in res.full_text:
        if not find_bot:
            click.echo("Please choose a bot.")
        res = choose_bot(context, res, find=find_bot)

    return res


def prompt_echo(
        context: Context,
        output: Response,
        success: Pattern = None,
        failure: Pattern = None,
        repeat: Pattern = None,
        force_newline: bool = False
):
    """ Prompts with BotFather's question """
    success = re.compile(success, re.IGNORECASE) if success else None
    failure = re.compile(failure, re.IGNORECASE) if failure else None
    repeat = re.compile(repeat, re.IGNORECASE) if repeat else None

    user_input = click.prompt(output.full_text)

    res = context.client.send_message_await(user_input)

    if repeat:
        while repeat.search(res.full_text):
            user_input = click.prompt(res.full_text)
            res = context.client.send_message_await(user_input)

    if success:
        if not success.search(res.full_text):
            return disconnect(context, error=res.full_text)
    if failure:
        if failure.search(res.full_text):
            return disconnect(context, error=res.full_text)

    if force_newline or len(res.full_text.split('\n')) >= 2:
        click.echo()

    return res


@cli.command()
@click.argument('bot', required=False)
@pass_context
def token(context: Context, bot: str = None):
    res = init_command(context, 'token', find_bot=bot)
    click.echo(res)
    disconnect(context)


@cli.command()
@click.argument('bot', required=False)
@pass_context
def revoke(context: Context, bot: str = None):
    res = init_command(context, 'revoke', find_bot=bot)
    click.echo(res)
    disconnect(context)


@cli.command()
@click.argument('bot', required=False)
@pass_context
def setdescription(context: Context, bot: str = None):
    res = init_command(context, 'setdescription', find_bot=bot)
    click.echo(res.full_text)
    description = click.prompt("Description")
    res = context.client.send_message_await(description, num_expected=1)
    click.echo(res)
    disconnect(context)


@cli.command()
@click.argument('bot', required=False)
@pass_context
def setname(context: Context, bot: str = None):
    res = init_command(context, 'setname', find_bot=bot)
    click.echo(res.full_text)
    name = click.prompt("Name")
    res = context.client.send_message_await(name, num_expected=1)
    click.echo(res)
    disconnect(context)


@cli.command()
@click.argument('bot', required=False)
@pass_context
def setabouttext(context: Context, bot: str = None):
    res = init_command(context, 'setabouttext', find_bot=bot)
    click.echo(res.full_text)
    about = click.prompt("About Text")
    res = context.client.send_message_await(about, num_expected=1)
    click.echo(res)
    disconnect(context)


@cli.command()
@pass_context
def newbot(context: Context):
    res = init_command(context, 'newbot')

    if not res.full_text.startswith('Alright, a new bot.'):
        return disconnect(context, error=res.full_text)

    name = prompt_echo(context, res, success=r'choose a username')
    username = prompt_echo(context, name, repeat=r'sorry')
    click.echo(username.full_text)


@cli.command()
@click.argument('bot', required=False)
@pass_context
def deletebot(context: Context, bot: str = None):
    init_command(context, 'deletebot', find_bot=bot)
    confirm = click.confirm(f"Delete {context.bot}, you sure?")
    if confirm:
        res = context.client.send_message_await('Yes, I am totally sure.')
        disconnect(context, message=res.full_text)
    else:
        disconnect(context, error='Aborted.')


@pass_context
def main(context: Context):
    cli(sys.argv[1:])
    disconnect(context)


if __name__ == '__main__':
    main()
