"""
Fabula Marketing Website - Wagtail Page Models

This module defines the marketing website pages for Fabula.
The marketing site presents Fabula as a product for Hollywood production teams.

Page Hierarchy:
- MarketingHomePage (site root)
  - FlexibleContentPage (Product, About pages)
  - DemoRequestPage (lead capture)
  - PricingPage (structured pricing tiers)
  - FAQPage (FAQ with sections)
  - UseCasesIndexPage (container)
    - UseCasePage (individual use cases)
  - narrative.SeriesIndexPage (moved here as 'explore')
"""

from django.db import models

from wagtail.models import Page
from wagtail.fields import RichTextField, StreamField
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.contrib.forms.models import AbstractEmailForm, AbstractFormField
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock

from modelcluster.fields import ParentalKey


# =============================================================================
# STREAMFIELD BLOCKS
# =============================================================================

class CTABlock(blocks.StructBlock):
    """Call-to-action button."""
    text = blocks.CharBlock(max_length=50, help_text="Button text")
    url = blocks.URLBlock(required=False, help_text="External URL")
    page = blocks.PageChooserBlock(required=False, help_text="Internal page link")
    style = blocks.ChoiceBlock(
        choices=[
            ('primary', 'Primary (Amber)'),
            ('secondary', 'Secondary (Outlined)'),
            ('ghost', 'Ghost (Text only)'),
        ],
        default='primary'
    )

    class Meta:
        icon = 'link'
        label = 'Call to Action'


class HeroBlock(blocks.StructBlock):
    """Hero section with headline, subheadline, and CTAs."""
    headline = blocks.CharBlock(
        max_length=100,
        help_text="Main headline (e.g., 'Never Lose Track of Your Story Again')"
    )
    subheadline = blocks.TextBlock(
        required=False,
        help_text="Supporting text below headline"
    )
    primary_cta = CTABlock(required=False)
    secondary_cta = CTABlock(required=False)
    supporting_copy = blocks.TextBlock(
        required=False,
        help_text="Additional context (e.g., social proof snippet)"
    )
    background_style = blocks.ChoiceBlock(
        choices=[
            ('gradient', 'Gradient Background'),
            ('dark', 'Dark Background'),
            ('image', 'Background Image'),
        ],
        default='gradient'
    )
    background_image = ImageChooserBlock(required=False)

    class Meta:
        icon = 'title'
        label = 'Hero Section'
        template = 'marketing/blocks/hero_block.html'


class FeatureBlock(blocks.StructBlock):
    """Single feature with icon, title, and description."""
    icon = blocks.CharBlock(
        max_length=50,
        help_text="Lucide icon name (e.g., 'zap', 'search', 'shield')"
    )
    title = blocks.CharBlock(max_length=100)
    description = blocks.TextBlock()

    class Meta:
        icon = 'pick'
        label = 'Feature'


class FeatureGridBlock(blocks.StructBlock):
    """Grid of features with section title."""
    section_title = blocks.CharBlock(max_length=100, required=False)
    section_subtitle = blocks.TextBlock(required=False)
    features = blocks.ListBlock(FeatureBlock())
    columns = blocks.ChoiceBlock(
        choices=[
            ('2', '2 Columns'),
            ('3', '3 Columns'),
            ('4', '4 Columns'),
        ],
        default='3'
    )

    class Meta:
        icon = 'grip'
        label = 'Feature Grid'
        template = 'marketing/blocks/feature_grid_block.html'


class ScenarioBlock(blocks.StructBlock):
    """A problem scenario with old way / new way comparison."""
    title = blocks.CharBlock(
        max_length=150,
        help_text="Scenario headline (e.g., 'Wait, Did We Already Do That?')"
    )
    description = blocks.TextBlock(
        help_text="Describe the problem situation"
    )
    question = blocks.CharBlock(
        max_length=200,
        required=False,
        help_text="The 'What if...' question"
    )

    class Meta:
        icon = 'warning'
        label = 'Problem Scenario'


class ProblemSolutionBlock(blocks.StructBlock):
    """Problem/solution section with scenarios."""
    section_title = blocks.CharBlock(
        max_length=100,
        help_text="Section headline (e.g., 'You Know These Moments')"
    )
    scenarios = blocks.ListBlock(ScenarioBlock())

    class Meta:
        icon = 'doc-full-inverse'
        label = 'Problem/Solution Section'
        template = 'marketing/blocks/problem_solution_block.html'


class TestimonialBlock(blocks.StructBlock):
    """A customer testimonial."""
    quote = blocks.TextBlock()
    author_name = blocks.CharBlock(max_length=100)
    author_role = blocks.CharBlock(max_length=100, required=False)
    author_company = blocks.CharBlock(max_length=100, required=False)
    author_image = ImageChooserBlock(required=False)

    class Meta:
        icon = 'openquote'
        label = 'Testimonial'


class StatBlock(blocks.StructBlock):
    """A single statistic."""
    value = blocks.CharBlock(
        max_length=20,
        help_text="The number/value (e.g., '5,287', '3.6x', '90%+')"
    )
    label = blocks.CharBlock(max_length=100)

    class Meta:
        icon = 'order'
        label = 'Statistic'


class SocialProofBlock(blocks.StructBlock):
    """Social proof section with testimonials and/or stats."""
    section_title = blocks.CharBlock(max_length=100, required=False)
    section_subtitle = blocks.TextBlock(required=False)
    stats = blocks.ListBlock(StatBlock(), required=False)
    testimonials = blocks.ListBlock(TestimonialBlock(), required=False)
    show_logos = blocks.BooleanBlock(
        default=False,
        required=False,
        help_text="Show client/partner logos"
    )

    class Meta:
        icon = 'group'
        label = 'Social Proof Section'
        template = 'marketing/blocks/social_proof_block.html'


class CTABannerBlock(blocks.StructBlock):
    """Full-width call-to-action banner."""
    headline = blocks.CharBlock(max_length=150)
    subtext = blocks.TextBlock(required=False)
    cta = CTABlock()
    style = blocks.ChoiceBlock(
        choices=[
            ('gradient', 'Gradient Background'),
            ('dark', 'Dark Background'),
            ('accent', 'Accent Color'),
        ],
        default='gradient'
    )

    class Meta:
        icon = 'placeholder'
        label = 'CTA Banner'
        template = 'marketing/blocks/cta_banner_block.html'


class FAQItemBlock(blocks.StructBlock):
    """Single FAQ question and answer."""
    question = blocks.CharBlock(max_length=300)
    answer = blocks.RichTextBlock()

    class Meta:
        icon = 'help'
        label = 'FAQ Item'


class FAQSectionBlock(blocks.StructBlock):
    """FAQ section with optional category grouping."""
    section_title = blocks.CharBlock(max_length=100, required=False)
    category = blocks.CharBlock(
        max_length=50,
        required=False,
        help_text="Category name for grouping (e.g., 'Security', 'Pricing')"
    )
    items = blocks.ListBlock(FAQItemBlock())

    class Meta:
        icon = 'help'
        label = 'FAQ Section'
        template = 'marketing/blocks/faq_section_block.html'


class RichTextSectionBlock(blocks.StructBlock):
    """Generic rich text section with optional title."""
    section_title = blocks.CharBlock(max_length=100, required=False)
    content = blocks.RichTextBlock()
    alignment = blocks.ChoiceBlock(
        choices=[
            ('left', 'Left'),
            ('center', 'Center'),
        ],
        default='left'
    )

    class Meta:
        icon = 'doc-full'
        label = 'Rich Text Section'
        template = 'marketing/blocks/rich_text_section_block.html'


class StepBlock(blocks.StructBlock):
    """A single step in a process."""
    number = blocks.CharBlock(max_length=10, help_text="Step number or label")
    title = blocks.CharBlock(max_length=100)
    description = blocks.TextBlock()
    icon = blocks.CharBlock(max_length=50, required=False, help_text="Lucide icon name")

    class Meta:
        icon = 'list-ol'
        label = 'Step'


class HowItWorksBlock(blocks.StructBlock):
    """How it works section with numbered steps."""
    section_title = blocks.CharBlock(max_length=100)
    section_subtitle = blocks.TextBlock(required=False)
    steps = blocks.ListBlock(StepBlock())
    closing_text = blocks.TextBlock(
        required=False,
        help_text="The 'magic' explanation at the end"
    )

    class Meta:
        icon = 'list-ol'
        label = 'How It Works'
        template = 'marketing/blocks/how_it_works_block.html'


class RoleBlock(blocks.StructBlock):
    """Content targeted at a specific role."""
    role_title = blocks.CharBlock(
        max_length=50,
        help_text="Role name (e.g., 'For Showrunners')"
    )
    description = blocks.TextBlock()
    example_queries = blocks.ListBlock(
        blocks.CharBlock(max_length=200),
        required=False,
        help_text="Example searches or questions this role would ask"
    )
    benefit_statement = blocks.CharBlock(
        max_length=200,
        required=False,
        help_text="Summary benefit (e.g., 'Instant answers backed by data')"
    )

    class Meta:
        icon = 'user'
        label = 'Role'


class AudienceSectionBlock(blocks.StructBlock):
    """Who it's for section with role-specific content."""
    section_title = blocks.CharBlock(max_length=100)
    roles = blocks.ListBlock(RoleBlock())

    class Meta:
        icon = 'group'
        label = 'Audience Section'
        template = 'marketing/blocks/audience_section_block.html'


class DifferentiatorBlock(blocks.StructBlock):
    """A single product differentiator."""
    title = blocks.CharBlock(max_length=150)
    description = blocks.TextBlock()
    why_it_matters = blocks.TextBlock(
        required=False,
        help_text="'Why it matters:' explanation"
    )

    class Meta:
        icon = 'tick'
        label = 'Differentiator'


class DifferentiatorsBlock(blocks.StructBlock):
    """What makes us different section."""
    section_title = blocks.CharBlock(max_length=100)
    section_subtitle = blocks.TextBlock(required=False)
    differentiators = blocks.ListBlock(DifferentiatorBlock())

    class Meta:
        icon = 'tick-inverse'
        label = 'Differentiators Section'
        template = 'marketing/blocks/differentiators_block.html'


# =============================================================================
# MARKETING STREAMFIELD DEFINITION
# =============================================================================

MARKETING_BLOCKS = [
    ('hero', HeroBlock()),
    ('feature_grid', FeatureGridBlock()),
    ('problem_solution', ProblemSolutionBlock()),
    ('social_proof', SocialProofBlock()),
    ('cta_banner', CTABannerBlock()),
    ('faq_section', FAQSectionBlock()),
    ('rich_text', RichTextSectionBlock()),
    ('how_it_works', HowItWorksBlock()),
    ('audience', AudienceSectionBlock()),
    ('differentiators', DifferentiatorsBlock()),
]


# =============================================================================
# PAGE MODELS
# =============================================================================

class MarketingHomePage(Page):
    """
    Marketing homepage - the root of the marketing site.

    Uses StreamField for flexible section composition.
    max_count = 1 ensures only one homepage exists.
    """
    tagline = models.CharField(
        max_length=200,
        blank=True,
        help_text="Site tagline shown in header/footer"
    )
    body = StreamField(
        MARKETING_BLOCKS,
        blank=True,
        use_json_field=True,
        help_text="Build the homepage from sections"
    )

    # SEO fields
    meta_description = models.TextField(
        blank=True,
        help_text="SEO meta description"
    )
    og_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Social sharing image"
    )

    content_panels = Page.content_panels + [
        FieldPanel('tagline'),
        FieldPanel('body'),
    ]

    promote_panels = Page.promote_panels + [
        FieldPanel('meta_description'),
        FieldPanel('og_image'),
    ]

    # Page hierarchy constraints
    max_count = 1
    subpage_types = [
        'marketing.FlexibleContentPage',
        'marketing.DemoRequestPage',
        'marketing.PricingPage',
        'marketing.FAQPage',
        'marketing.UseCasesIndexPage',
        'narrative.SeriesIndexPage',  # Graph explorer lives under marketing
    ]
    parent_page_types = ['wagtailcore.Page']  # Can only be at root

    class Meta:
        verbose_name = "Marketing Homepage"

    def get_template(self, request, *args, **kwargs):
        """Use YAML-driven homepage template."""
        return 'marketing/homepage_page.html'

    def get_context(self, request):
        context = super().get_context(request)
        # Make series available for navigation
        from narrative.models import SeriesIndexPage
        context['available_series'] = SeriesIndexPage.objects.live()
        return context


class FlexibleContentPage(Page):
    """
    Generic marketing page with StreamField content.

    Used for: Product, About, and other marketing pages.
    """
    subtitle = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional subtitle shown below title"
    )
    body = StreamField(
        MARKETING_BLOCKS,
        blank=True,
        use_json_field=True
    )

    # SEO fields
    meta_description = models.TextField(blank=True)
    og_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )

    content_panels = Page.content_panels + [
        FieldPanel('subtitle'),
        FieldPanel('body'),
    ]

    promote_panels = Page.promote_panels + [
        FieldPanel('meta_description'),
        FieldPanel('og_image'),
    ]

    subpage_types = ['marketing.FlexibleContentPage']
    parent_page_types = ['marketing.MarketingHomePage', 'marketing.FlexibleContentPage']

    def get_template(self, request, *args, **kwargs):
        """Return custom templates for specific pages.

        YAML-driven pages load content via {% load_content 'slug' %} template
        tag from content/<slug>.yaml files.
        """
        slug_templates = {
            # Legacy hardcoded templates
            'product': 'marketing/product_page.html',
            # YAML-driven pages (content in content/<slug>.yaml)
            'about': 'marketing/about_page_yaml.html',
            'platform': 'marketing/platform_page.html',
            'for-production': 'marketing/for_production_page.html',
            'benchmarks': 'marketing/benchmarks_page.html',
            'early-access': 'marketing/early_access_page.html',
        }
        if self.slug in slug_templates:
            return slug_templates[self.slug]
        return super().get_template(request, *args, **kwargs)

    class Meta:
        verbose_name = "Marketing Page"


# =============================================================================
# PRICING PAGE
# =============================================================================

class PricingTierBlock(blocks.StructBlock):
    """A single pricing tier."""
    name = blocks.CharBlock(max_length=50, help_text="Tier name (e.g., 'Pilot')")
    price = blocks.CharBlock(
        max_length=50,
        help_text="Price display (e.g., '$XXX per script', 'Contact Us')"
    )
    description = blocks.TextBlock(required=False)
    features = blocks.ListBlock(
        blocks.CharBlock(max_length=200),
        help_text="List of included features"
    )
    cta = CTABlock(required=False)
    highlighted = blocks.BooleanBlock(
        default=False,
        required=False,
        help_text="Highlight this tier as recommended"
    )

    class Meta:
        icon = 'tag'
        label = 'Pricing Tier'


class PricingPage(Page):
    """
    Pricing page with structured tiers.
    """
    introduction = RichTextField(
        blank=True,
        help_text="Introduction text above pricing tiers"
    )
    tiers = StreamField(
        [('tier', PricingTierBlock())],
        blank=True,
        use_json_field=True
    )
    footer_note = RichTextField(
        blank=True,
        help_text="Additional notes below pricing (e.g., 'Try It Free')"
    )

    # SEO
    meta_description = models.TextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('introduction'),
        FieldPanel('tiers'),
        FieldPanel('footer_note'),
    ]

    promote_panels = Page.promote_panels + [
        FieldPanel('meta_description'),
    ]

    max_count = 1
    subpage_types = []
    parent_page_types = ['marketing.MarketingHomePage']

    class Meta:
        verbose_name = "Pricing Page"


# =============================================================================
# FAQ PAGE
# =============================================================================

class FAQPage(Page):
    """
    FAQ page with grouped questions.
    """
    introduction = RichTextField(
        blank=True,
        help_text="Introduction text above FAQ sections"
    )
    sections = StreamField(
        [('section', FAQSectionBlock())],
        blank=True,
        use_json_field=True
    )

    # SEO
    meta_description = models.TextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('introduction'),
        FieldPanel('sections'),
    ]

    promote_panels = Page.promote_panels + [
        FieldPanel('meta_description'),
    ]

    max_count = 1
    subpage_types = []
    parent_page_types = ['marketing.MarketingHomePage']

    class Meta:
        verbose_name = "FAQ Page"


# =============================================================================
# USE CASES
# =============================================================================

class UseCasesIndexPage(Page):
    """
    Index page for use cases.
    """
    introduction = RichTextField(
        blank=True,
        help_text="Introduction text for use cases section"
    )

    content_panels = Page.content_panels + [
        FieldPanel('introduction'),
    ]

    subpage_types = ['marketing.UseCasePage']
    parent_page_types = ['marketing.MarketingHomePage']

    class Meta:
        verbose_name = "Use Cases Index"

    def get_use_cases(self):
        return UseCasePage.objects.live().child_of(self)


class UseCasePage(Page):
    """
    Individual use case page.

    Structure: Situation -> Old Way -> Fabula Way -> Result
    """
    tagline = models.CharField(
        max_length=200,
        blank=True,
        help_text="Short tagline for card display"
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Lucide icon name for this use case"
    )

    # Structured content
    situation = RichTextField(
        help_text="The situation (e.g., 'You're a showrunner breaking Season 4...')"
    )
    old_way = RichTextField(
        help_text="How it's done without Fabula (bullet points work well)"
    )
    fabula_way = RichTextField(
        help_text="How Fabula solves it"
    )
    result = RichTextField(
        help_text="The outcome/benefit"
    )
    real_example = models.TextField(
        blank=True,
        help_text="A concrete example quote"
    )

    # Optional additional content
    additional_content = StreamField(
        MARKETING_BLOCKS,
        blank=True,
        use_json_field=True
    )

    # SEO
    meta_description = models.TextField(blank=True)

    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel('tagline'),
            FieldPanel('icon'),
        ], heading="Display Settings"),
        MultiFieldPanel([
            FieldPanel('situation'),
            FieldPanel('old_way'),
            FieldPanel('fabula_way'),
            FieldPanel('result'),
            FieldPanel('real_example'),
        ], heading="Use Case Content"),
        FieldPanel('additional_content'),
    ]

    promote_panels = Page.promote_panels + [
        FieldPanel('meta_description'),
    ]

    subpage_types = []
    parent_page_types = ['marketing.UseCasesIndexPage']

    class Meta:
        verbose_name = "Use Case"


# =============================================================================
# DEMO REQUEST (FORM PAGE)
# =============================================================================

class DemoFormField(AbstractFormField):
    """Form field for demo request form."""
    page = ParentalKey(
        'DemoRequestPage',
        on_delete=models.CASCADE,
        related_name='form_fields'
    )


class DemoRequestPage(AbstractEmailForm):
    """
    Demo request form page with lead capture.
    """
    intro_headline = models.CharField(
        max_length=200,
        default="See Your Show in a New Way"
    )
    intro_subheadline = models.TextField(
        blank=True,
        default="Upload a sample script and we'll show you what Fabula can do."
    )
    introduction = RichTextField(
        blank=True,
        help_text="Additional text above the form"
    )
    thank_you_headline = models.CharField(
        max_length=200,
        default="Thank You!"
    )
    thank_you_text = RichTextField(
        blank=True,
        help_text="Message shown after form submission"
    )

    # Alternative CTA
    alternative_cta_text = models.CharField(
        max_length=200,
        blank=True,
        help_text="Alternative action text (e.g., 'Or explore our interactive demo')"
    )
    alternative_cta_url = models.URLField(
        blank=True,
        help_text="URL for alternative CTA"
    )

    # SEO
    meta_description = models.TextField(blank=True)

    content_panels = AbstractEmailForm.content_panels + [
        MultiFieldPanel([
            FieldPanel('intro_headline'),
            FieldPanel('intro_subheadline'),
            FieldPanel('introduction'),
        ], heading="Introduction"),
        InlinePanel('form_fields', label="Form Fields"),
        MultiFieldPanel([
            FieldPanel('thank_you_headline'),
            FieldPanel('thank_you_text'),
        ], heading="Thank You Message"),
        MultiFieldPanel([
            FieldPanel('alternative_cta_text'),
            FieldPanel('alternative_cta_url'),
        ], heading="Alternative CTA"),
    ]

    promote_panels = AbstractEmailForm.promote_panels + [
        FieldPanel('meta_description'),
    ]

    max_count = 1
    subpage_types = []
    parent_page_types = ['marketing.MarketingHomePage']

    class Meta:
        verbose_name = "Demo Request Page"

    def get_context(self, request):
        context = super().get_context(request)
        # Check if form was submitted
        context['form_submitted'] = request.GET.get('submitted') == 'true'
        return context
