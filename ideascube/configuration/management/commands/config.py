import argparse
import ast

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from ideascube.configuration import get_config, reset_config, set_config
from ideascube.configuration.exceptions import (
    InvalidConfigurationValueError,
    NoSuchConfigurationKeyError,
    NoSuchConfigurationNamespaceError,
    )
from ideascube.configuration.registry import (
    get_all_namespaces, get_config_data, get_namespaced_configs,
    )


class Command(BaseCommand):
    help = 'Manage server configuration'

    def add_arguments(self, parser):
        subs = parser.add_subparsers(
            title='Commands', dest='cmd', metavar='',
            parser_class=argparse.ArgumentParser)

        get = subs.add_parser(
            'get', help='Get the current value of a configuration option')
        get.add_argument('namespace', help='The configuration namespace')
        get.add_argument('key', help='The configuration key')
        get.set_defaults(func=self.get_config)

        describe = subs.add_parser(
            'describe', help='Describe a configuration option')
        describe.add_argument('namespace', help='The configuration namespace')
        describe.add_argument('key', help='The configuration key')
        describe.set_defaults(func=self.describe_config)

        list = subs.add_parser(
            'list', help='List configuration namespaces and keys')
        list.add_argument(
            'namespace', nargs='?',
            help='Only list configuration keys for this namespace')
        list.set_defaults(func=self.list_configs)

        reset = subs.add_parser(
            'reset', help='Reset a configuration option to its default value')
        reset.add_argument('namespace', help='The configuration namespace')
        reset.add_argument('key', help='The configuration key')
        reset.set_defaults(func=self.reset_config)

        set = subs.add_parser(
            'set', help='Set the value of a configuration option')
        set.add_argument('namespace', help='The configuration namespace')
        set.add_argument('key', help='The configuration key')
        set.add_argument('value', help='The new value')
        set.set_defaults(func=self.set_config)

        self.parser = parser

    def handle(self, *_, **options):
        if 'func' not in options:
            self.parser.print_help()
            self.parser.exit(1)

        options['func'](options)

    def _evaluate_value(self, value):
        if value in ('true', 'false'):
            # Special case booleans for a better UX
            value = value.capitalize()

        try:
            return ast.literal_eval(value)

        except (SyntaxError, ValueError):
            # Admin probably wanted a string and didn't use enough quotes
            # examples:
            #     $ ideascube config set server site-name thename
            #     $ ideascube config set server site-name 'the name'
            return str(value)

    def get_config(self, options):
        namespace = options['namespace']
        key = options['key']

        try:
            value = get_config(namespace, key)

        except (NoSuchConfigurationNamespaceError,
                NoSuchConfigurationKeyError) as e:
            raise CommandError(e)

        print('%r' % value)

    def describe_config(self, options):
        data = {
            'namespace': options['namespace'],
            'key': options['key'],
        }

        try:
            data.update(get_config_data(data['namespace'], data['key']))

        except (NoSuchConfigurationNamespaceError,
                NoSuchConfigurationKeyError) as e:
            raise CommandError(e)

        print(
            '# {namespace} {key}\n\n'
            '{summary}\n\n'
            '* type: {pretty_type}\n'
            '* default value: {default!r}'.format(**data))

    def list_configs(self, options):
        namespace = options['namespace']

        if namespace is None:
            for namespace in get_all_namespaces():
                print(namespace)

            return

        try:
            for key in get_namespaced_configs(namespace):
                print("%s %s" % (namespace, key))

        except NoSuchConfigurationNamespaceError as e:
            raise CommandError(e)

    def reset_config(self, options):
        namespace = options['namespace']
        key = options['key']

        try:
            reset_config(namespace, key)

        except (NoSuchConfigurationNamespaceError,
                NoSuchConfigurationKeyError) as e:
            raise CommandError(e)

    def set_config(self, options):
        namespace = options['namespace']
        key = options['key']
        value = self._evaluate_value(options['value'])
        system_user = get_user_model().objects.get_system_user()

        try:
            set_config(namespace, key, value, system_user)

        except (InvalidConfigurationValueError,
                NoSuchConfigurationNamespaceError,
                NoSuchConfigurationKeyError) as e:
            raise CommandError(e)
