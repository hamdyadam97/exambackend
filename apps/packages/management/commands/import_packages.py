"""Create packages from a JSON list: name, price, period_days, path [category names, level 1 first],
active, is_trial, number_of_questions. Matched by name + category, so it can be re-run; existing
packages are left as they are (they may have been edited in the dashboard)."""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.content.models import Category
from apps.packages.models import Package


class Command(BaseCommand):
    help = 'Import packages from a JSON file (see module docstring).'

    def add_arguments(self, parser):
        parser.add_argument('path')

    @transaction.atomic
    def handle(self, path, **options):
        records = json.load(open(path, encoding='utf-8'))
        created = skipped = 0
        for r in records:
            category = None
            for name in r['path']:
                category = Category.objects.filter(name=name, parent=category).first()
                if category is None:
                    raise CommandError(f'{r["name"]}: category "{name}" not found under {r["path"]}; run seed_taxonomy.')
            _, is_new = Package.objects.get_or_create(
                name=r['name'], category=category, deleted_at__isnull=True,
                defaults={
                    'price': r['price'],
                    'period_days': r.get('period_days'),
                    'number_of_questions': r.get('number_of_questions'),
                    'is_trial': bool(r.get('is_trial')),
                    'status': Package.ACTIVE if r.get('active', True) else Package.INACTIVE,
                },
            )
            created += is_new
            skipped += not is_new
        self.stdout.write(self.style.SUCCESS(f'Created {created} packages, {skipped} already there.'))
