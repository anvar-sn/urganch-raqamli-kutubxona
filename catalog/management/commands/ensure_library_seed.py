import os
import secrets
from pathlib import Path
from django.core.management import call_command
from django.core.management.base import BaseCommand
from catalog.models import Book, Category, Quiz, User


class Command(BaseCommand):
    help = 'Seed initial library books, categories, quizzes, and default admin on fresh deploy.'

    def handle(self, *args, **options):
        seed_path = Path(__file__).resolve().parents[2] / 'data' / 'initial_library_seed.json'

        if Category.objects.count() == 0 and Book.objects.count() == 0 and Quiz.objects.count() == 0:
            if seed_path.exists():
                self.stdout.write(f'Loading seed data from {seed_path.name}...')
                call_command('loaddata', str(seed_path), verbosity=1)
        else:
            self.stdout.write('Library database already has records; skipping seed loaddata.')

        if User.objects.count() == 0:
            pwd = os.getenv('DJANGO_ADMIN_PASSWORD', '').strip()
            if not pwd:
                pwd = secrets.token_urlsafe(14)
            User.objects.create_superuser(
                username='admin',
                password=pwd,
                first_name='Boshqaruvchi',
                role='librarian',
            )
            self.stdout.write('Created initial admin account (@admin).')
