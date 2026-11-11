from django.core.management.base import BaseCommand
from django.db import transaction

from apps.content.models import Category, ExamSection, QuestionsTopic
from apps.content.taxonomy import ROOT_RENAMES, SECTIONS, TREE


class Command(BaseCommand):
    help = 'Create the exam categories, shared sections and their topics (idempotent: never deletes or renames).'

    @transaction.atomic
    def handle(self, *args, **options):
        created = {'categories': 0, 'sections': 0, 'topics': 0}

        def node(name, parent, level, order):
            obj, is_new = Category.objects.get_or_create(
                name=name, parent=parent, level=level,
                defaults={'order': order, 'status': Category.ACTIVE},
            )
            created['categories'] += is_new
            return obj

        for old, new in ROOT_RENAMES.items():
            roots = Category.objects.filter(parent=None, level=Category.LEVEL_CATEGORY)
            if not roots.filter(name=new).exists():
                renamed = roots.filter(name=old).update(name=new)
                if renamed:
                    self.stdout.write(f'Renamed category "{old}" -> "{new}"')

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
                if not is_new and topic.section_id is None:
                    topic.section = section
                    topic.save(update_fields=['section'])

        self.stdout.write(self.style.SUCCESS(
            'Created {categories} categories, {sections} sections, {topics} topics.'.format(**created)
        ))
