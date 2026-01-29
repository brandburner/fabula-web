"""
Management command to set up the marketing page structure.

This command:
1. Creates a MarketingHomePage as the new site root
2. Moves the existing SeriesIndexPage under marketing home with slug 'explore'
3. Creates placeholder marketing pages (Product, Pricing, FAQ, etc.)
4. Updates the Site settings to use MarketingHomePage as root

Usage:
    python manage.py setup_marketing_pages
    python manage.py setup_marketing_pages --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from wagtail.models import Page, Site

from marketing.models import (
    MarketingHomePage, FlexibleContentPage, PricingPage,
    FAQPage, UseCasesIndexPage, UseCasePage, DemoRequestPage
)
from narrative.models import SeriesIndexPage


class Command(BaseCommand):
    help = 'Set up the marketing website page structure'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))

        try:
            with transaction.atomic():
                self._setup_pages(dry_run)

                if dry_run:
                    # Rollback in dry-run mode
                    raise DryRunComplete()

        except DryRunComplete:
            self.stdout.write(self.style.SUCCESS('\nDry run complete. No changes made.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
            raise

    def _setup_pages(self, dry_run):
        """Create the marketing page structure."""

        # Get the Wagtail root page
        root_page = Page.objects.get(depth=1)
        self.stdout.write(f'Root page: {root_page}')

        # Check if MarketingHomePage already exists
        existing_home = MarketingHomePage.objects.first()
        if existing_home:
            self.stdout.write(self.style.WARNING(
                f'MarketingHomePage already exists: {existing_home.title}'
            ))
            marketing_home = existing_home
        else:
            # Find a unique slug - 'home' might be taken
            slug = 'fabula-home'
            # Check for existing pages with this slug at root level
            existing_slugs = set(
                Page.objects.filter(depth=2).values_list('slug', flat=True)
            )
            if slug in existing_slugs:
                # Try alternative slugs
                for i in range(1, 100):
                    test_slug = f'fabula-home-{i}'
                    if test_slug not in existing_slugs:
                        slug = test_slug
                        break

            # Create MarketingHomePage
            marketing_home = MarketingHomePage(
                title='Fabula',
                slug=slug,
                tagline='Your Show\'s Memory, Automated',
                meta_description='Fabula is the story bible that updates itself. '
                                 'From pilot to finale, know every character, every relationship, '
                                 'every detail—instantly.',
            )
            root_page.add_child(instance=marketing_home)
            self.stdout.write(self.style.SUCCESS(f'Created MarketingHomePage: {marketing_home.title} (slug: {slug})'))

        # Move existing SeriesIndexPage under marketing home
        existing_series = SeriesIndexPage.objects.first()
        if existing_series:
            self.stdout.write(f'Found existing SeriesIndexPage: {existing_series.title}')

            # Check if series is already under marketing home
            if existing_series.get_parent() == marketing_home:
                self.stdout.write('SeriesIndexPage is already under MarketingHomePage')
            else:
                # Move the series under marketing home
                # Note: We don't change the slug - it keeps its original slug
                # The catalog view at /explore/ is separate from Wagtail page serving
                self.stdout.write(f'Moving {existing_series.title} under MarketingHomePage...')
                if not dry_run:
                    existing_series.move(marketing_home, pos='last-child')
                    self.stdout.write(self.style.SUCCESS(
                        f'Moved {existing_series.title} under MarketingHomePage'
                    ))

        # Create Product page
        if not FlexibleContentPage.objects.filter(slug='product').exists():
            product_page = FlexibleContentPage(
                title='Product',
                slug='product',
                subtitle='Your Show\'s Memory, Automated',
                meta_description='Learn how Fabula builds and maintains your story bible automatically.',
            )
            marketing_home.add_child(instance=product_page)
            self.stdout.write(self.style.SUCCESS('Created Product page'))
        else:
            self.stdout.write('Product page already exists')

        # Create About page
        if not FlexibleContentPage.objects.filter(slug='about').exists():
            about_page = FlexibleContentPage(
                title='About',
                slug='about',
                subtitle='We Built This Because We Needed It',
                meta_description='Learn about the team behind Fabula.',
            )
            marketing_home.add_child(instance=about_page)
            self.stdout.write(self.style.SUCCESS('Created About page'))
        else:
            self.stdout.write('About page already exists')

        # Create Pricing page
        if not PricingPage.objects.exists():
            pricing_page = PricingPage(
                title='Pricing',
                slug='pricing',
                meta_description='Flexible pricing for pilots, seasons, and studio-wide deployment.',
            )
            marketing_home.add_child(instance=pricing_page)
            self.stdout.write(self.style.SUCCESS('Created Pricing page'))
        else:
            self.stdout.write('Pricing page already exists')

        # Create FAQ page
        if not FAQPage.objects.exists():
            faq_page = FAQPage(
                title='FAQ',
                slug='faq',
                meta_description='Frequently asked questions about Fabula.',
            )
            marketing_home.add_child(instance=faq_page)
            self.stdout.write(self.style.SUCCESS('Created FAQ page'))
        else:
            self.stdout.write('FAQ page already exists')

        # Create Demo Request page
        if not DemoRequestPage.objects.exists():
            demo_page = DemoRequestPage(
                title='Request a Demo',
                slug='demo',
                intro_headline='See Your Show in a New Way',
                intro_subheadline='Upload a sample script and we\'ll show you what Fabula can do with it—or explore our demo using The West Wing.',
                thank_you_headline='Thank You!',
                thank_you_text='<p>We\'ll be in touch within 24 hours to schedule your demo.</p>',
                alternative_cta_text='Or explore our interactive demo',
                meta_description='Request a personalized Fabula demo for your production.',
            )
            marketing_home.add_child(instance=demo_page)
            self.stdout.write(self.style.SUCCESS('Created Demo Request page'))
        else:
            self.stdout.write('Demo Request page already exists')

        # Create Use Cases index
        if not UseCasesIndexPage.objects.exists():
            use_cases_index = UseCasesIndexPage(
                title='Use Cases',
                slug='use-cases',
            )
            marketing_home.add_child(instance=use_cases_index)
            self.stdout.write(self.style.SUCCESS('Created Use Cases index'))

            # Create sample use cases
            use_cases_data = [
                {
                    'title': 'Breaking Season 4',
                    'slug': 'breaking-season-4',
                    'tagline': 'Speed up your writers\' room with instant show history access',
                    'icon': 'users',
                    'situation': '<p>You\'re a showrunner breaking Season 4 of a family drama. The room is full of writers—some are new, some have been here since Season 1. You need everyone on the same page, fast.</p>',
                    'old_way': '<ul><li>New writers binge all 36 episodes (72 hours of TV)</li><li>Someone maintains a "show wiki" that\'s always out of date</li><li>You\'re constantly answering "wait, what happened with...?" questions</li><li>Character relationships are in your head or scattered notes</li></ul>',
                    'fabula_way': '<ul><li>New writers search the show: "What\'s the mother-daughter conflict arc?"</li><li>Fabula shows every relevant scene with timestamps</li><li>Character relationship maps show who\'s connected and how</li><li>You search: "Unresolved story threads" and find setup you forgot</li></ul>',
                    'result': '<p>Writers onboard in 3 days instead of 3 weeks. The room breaks faster because everyone has instant access to show history.</p>',
                    'real_example': 'We set up that the brother was suspicious of the father in Season 2 but never resolved it. That\'s our Season 4 arc.',
                },
                {
                    'title': 'Legal Needs the Asset List',
                    'slug': 'legal-asset-list',
                    'tagline': 'Export complete character and location lists in minutes',
                    'icon': 'file-text',
                    'situation': '<p>Your hit show is going into international syndication. Legal needs a complete list of characters, locations, and objects for licensing and merchandising.</p>',
                    'old_way': '<ul><li>Script coordinator manually builds spreadsheets</li><li>Someone rewatches episodes to catch everything</li><li>"Wait, what about that bar they visited once in Season 1?"</li><li>Two weeks of tedious, error-prone work</li></ul>',
                    'fabula_way': '<ul><li>Click "Export all entities to Excel"</li><li>Filter by entity type (characters, locations, objects)</li><li>Every appearance, every description, automatically compiled</li><li>Legal has what they need in 10 minutes</li></ul>',
                    'result': '<p>What took two weeks now takes ten minutes. Zero errors, complete coverage.</p>',
                    'real_example': '',
                },
                {
                    'title': 'We Want to Do a Spinoff',
                    'slug': 'planning-spinoff',
                    'tagline': 'Find franchise potential with character network analysis',
                    'icon': 'git-branch',
                    'situation': '<p>Your show is a hit. The network wants a spinoff. Which character could carry their own series? What relationships have untapped potential?</p>',
                    'old_way': '<ul><li>Gut instinct and rewatching</li><li>"I feel like this character is interesting"</li><li>Guessing which dynamics have audience appeal</li><li>Risk of building a spinoff on a character with no depth</li></ul>',
                    'fabula_way': '<ul><li>Search: "Characters with high relationship density but low screen time"</li><li>Fabula shows supporting characters with rich networks</li><li>Visual maps reveal which character pairs have chemistry</li><li>Identify story threads you set up but never explored</li></ul>',
                    'result': '<p>Make franchise decisions with narrative data, not just intuition.</p>',
                    'real_example': 'This detective appeared in 8 episodes across 3 seasons, always had great scenes with the lead, but never got their own arc. That\'s the spinoff.',
                },
            ]

            for uc_data in use_cases_data:
                use_case = UseCasePage(
                    title=uc_data['title'],
                    slug=uc_data['slug'],
                    tagline=uc_data['tagline'],
                    icon=uc_data['icon'],
                    situation=uc_data['situation'],
                    old_way=uc_data['old_way'],
                    fabula_way=uc_data['fabula_way'],
                    result=uc_data['result'],
                    real_example=uc_data['real_example'],
                )
                use_cases_index.add_child(instance=use_case)
                self.stdout.write(self.style.SUCCESS(f'  Created use case: {uc_data["title"]}'))

        else:
            self.stdout.write('Use Cases index already exists')

        # Update Site to use marketing home as root
        site = Site.objects.filter(is_default_site=True).first()
        if site:
            if site.root_page != marketing_home:
                self.stdout.write(f'Updating site root from {site.root_page} to {marketing_home}')
                if not dry_run:
                    site.root_page = marketing_home
                    site.site_name = 'Fabula'
                    site.save()
                    self.stdout.write(self.style.SUCCESS('Updated Site settings'))
            else:
                self.stdout.write('Site already uses MarketingHomePage as root')
        else:
            self.stdout.write(self.style.WARNING('No default site found'))

        # Publish all pages
        if not dry_run:
            for page in Page.objects.filter(depth__gte=2):
                if not page.live:
                    revision = page.save_revision()
                    revision.publish()
                    self.stdout.write(f'Published: {page.title}')

        self.stdout.write(self.style.SUCCESS('\nMarketing page setup complete!'))
        self.stdout.write('\nPage structure:')
        self._print_page_tree(marketing_home, 0)

    def _print_page_tree(self, page, indent):
        """Print the page tree for verification."""
        prefix = '  ' * indent
        self.stdout.write(f'{prefix}- {page.title} ({page.slug})')
        for child in page.get_children():
            self._print_page_tree(child, indent + 1)


class DryRunComplete(Exception):
    """Exception to trigger rollback in dry-run mode."""
    pass
