from django.core.management.base import BaseCommand
from django.db import transaction

from apps.content.models import Blog, Category, ExamSection, QuestionsTopic
from apps.content.taxonomy import PRUNE_KEEP, ROOT_RENAMES, SECTIONS, TREE


def is_linked(category):
    """Anything that would lose data if this category were deleted."""
    from apps.exams.models import ExamTrail, Question
    from apps.packages.models import Package

    ids = [c.id for c in category.get_descendants(include_self=True)] + list(
        Category.objects.filter(parent__parent=category).values_list('id', flat=True)
    )
    return (
        Question.objects.filter(category_id__in=ids).exists()
        or Question.objects.filter(sub_category_id__in=ids).exists()
        or Question.objects.filter(sub_subcategory_id__in=ids).exists()
        or Package.objects.filter(category_id__in=ids).exists()
        or ExamTrail.objects.filter(categories__in=ids).exists()
        or ExamTrail.objects.filter(sub_categories__in=ids).exists()
        or ExamTrail.objects.filter(sub_sub_categories__in=ids).exists()
        # These cascade with the category, so deleting it would delete them too.
        or Blog.objects.filter(category_id__in=ids).exists()
        or ExamSection.objects.filter(category_id__in=ids).exists()
        or QuestionsTopic.objects.filter(category_id__in=ids).exists()
    )


class Command(BaseCommand):
    help = 'Create the exam categories, shared sections and their topics (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prune', action='store_true',
            help='Delete categories that are not in the tree, when nothing is linked to them.',
        )

    @transaction.atomic
    def handle(self, *args, prune=False, **options):
        created = {'categories': 0, 'sections': 0, 'topics': 0}
        keep = set()

        roots = Category.objects.filter(parent=None, level=Category.LEVEL_CATEGORY)
        for old, new in ROOT_RENAMES.items():
            if not roots.filter(name=new).exists() and roots.filter(name=old).update(name=new):
                self.stdout.write(f'Renamed category "{old}" -> "{new}"')

        def node(name, parent, level, order):
            obj, is_new = Category.objects.get_or_create(
                name=name, parent=parent, level=level,
                defaults={'order': order, 'status': Category.ACTIVE},
            )
            if not is_new and obj.order != order:
                obj.order = order
                obj.save(update_fields=['order'])
            created['categories'] += is_new
            keep.add(obj.id)
            return obj

        for i, (root_name, subs) in enumerate(TREE):
            root = node(root_name, None, Category.LEVEL_CATEGORY, i)
            for j, (sub_name, leaves) in enumerate(subs):
                sub = node(sub_name, root, Category.LEVEL_SUB_CATEGORY, j)
                for k, leaf_name in enumerate(leaves):
                    node(leaf_name, sub, Category.LEVEL_SUB_SUB_CATEGORY, k)

        for i, (section_name, topics) in enumerate(SECTIONS.items()):
            section, is_new = ExamSection.objects.get_or_create(
                name=section_name, category=None, defaults={'order': i, 'status': Category.ACTIVE},
            )
            created['sections'] += is_new
            for topic_name in topics:
                topic, is_new = QuestionsTopic.objects.get_or_create(topic=topic_name, defaults={'section': section})
                created['topics'] += is_new
                if not is_new and topic.section_id != section.id:
                    topic.section = section
                    topic.save(update_fields=['section'])

        pruned = 0
        if prune:
            # Deepest first, so a parent is only deleted once its children are gone.
            for category in Category.objects.exclude(id__in=keep).order_by('-level'):
                if category.parent_id is None and category.name in PRUNE_KEEP:
                    continue
                if not Category.objects.filter(pk=category.pk).exists():
                    continue
                if category.children.exists() or is_linked(category):
                    self.stdout.write(self.style.WARNING(f'Kept "{category.name}" (id {category.id}): still in use'))
                    continue
                category.delete()
                pruned += 1

        self.stdout.write(self.style.SUCCESS(
            'Created {categories} categories, {sections} sections, {topics} topics.'.format(**created)
            + (f' Removed {pruned} unused categories.' if prune else '')
        ))
