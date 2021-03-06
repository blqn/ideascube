# -*- coding: utf-8 -*-
import os
import sys

from django.core.management.base import BaseCommand
from django.utils.six.moves import input

from ideascube.serveradmin.backup import Backup


class Command(BaseCommand):
    help = "Manage server backups"

    def add_arguments(self, parser):
        parser.add_argument('action', default="list", nargs='?',
                            choices=['list', 'create', 'add', 'delete',
                                     'restore'],
                            help='Action to run. Default to "list".')
        parser.add_argument('reference', nargs='?',
                            help='Backup name or file path to be used for '
                            '"add", "delete" or "restore" action.')
        parser.add_argument('--format', default=None,
                            help='Backup file format. Possible values: {}'
                                 'Default: {}'.format(Backup.SUPPORTED_FORMATS_AT_CREATION,
                                                      Backup.FORMAT))

    def handle(self, *args, **options):
        format = options['format']
        action = options['action']
        supported_formats = (Backup.SUPPORTED_FORMATS_AT_CREATION
                                if action == 'create'
                                else Backup.SUPPORTED_FORMATS )
        if format and format not in supported_formats:
            self.stderr.write('Unsupported format: {}'.format(format))
            sys.exit(1)
        reference = options['reference']
        interactive = options.get('interactive')
        if action == 'list':
            self.stdout.write('* Available backups:')
            for backup in Backup.list():
                self.stdout.write(str(backup))
        elif action == 'create':
            backup = Backup.create(format=format)
            self.stdout.write('Succesfully created backup {}'.format(backup))
        elif action == 'add':
            if not reference:
                self.stderr.write('Missing path to archive backup to add.')
                sys.exit(1)
            if not os.path.exists(reference):
                self.stderr.write('File not found {}'.format(reference))
            self.add(reference)
        elif action == 'restore':
            if not reference:
                self.stderr.write('Missing backup path or id to restore.')
                sys.exit(1)
            if Backup.exists(reference):
                backup = Backup(reference)
            elif os.path.exists(reference):
                backup = self.add(reference)
            else:
                self.stderr.write('Unable to understand backup reference {}. '
                                  'Please pass either a backup name or a '
                                  'filepath.'.format(reference))
                sys.exit(1)
            if interactive:
                confirm = input('You have requested to restore {}. This will '
                                'replace all the server data, including '
                                'database and medias.\n'
                                'Type "yes" to confirm or "no" to '
                                'cancel: '.format(backup))
                if confirm != 'yes':
                    self.stderr.write("Restore cancelled.")
                    sys.exit(1)
            backup.restore()
            self.stdout.write('Succesfully restored {}!'.format(backup))

    def add(self, filepath):
        with open(filepath, 'rb') as f:
            backup = Backup.load(f)
            self.stdout.write(u"✔ Imported backup {}.".format(backup))
            return backup
