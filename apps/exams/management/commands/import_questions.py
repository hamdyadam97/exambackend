"""Import the cleaned question bank (JSON made from the old platform's export).

Each record: source_id, text, options, correct, explanation, hint, path [root, sub, l3|None],
exam_year, active_before, problems, fixed_order, and optionally section / topic.

Re-runnable: questions are matched by source_id. A question already in the database is left as it is
(it may have been edited in the dashboard); only new ones are created. Run seed_taxonomy first.
"""
import gzip
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.content.models import Category, ExamSection, QuestionsTopic
from apps.exams.models import Answer, ExamSectionLink, Question, QuestionTopic

CHUNK = 1000


class Command(BaseCommand):
    help = 'Import questions from a cleaned JSON file (see module docstring).'

    def add_arguments(self, parser):
        parser.add_argument('path')
        parser.add_argument('--dry-run', action='store_true', help='Validate and count, write nothing.')

    def handle(self, path, dry_run=False, **options):
        opener = gzip.open if path.endswith('.gz') else open
        with opener(path, 'rt', encoding='utf-8') as f:
            records = json.load(f)
        nodes = self.category_lookup()
        sections = {s.name: s.id for s in ExamSection.objects.filter(category=None)}
        topics = {(t.section_id, t.topic): t.id for t in QuestionsTopic.objects.all()}
        existing = set(Question.objects.filter(source_id__isnull=False).values_list('source_id', flat=True))

        todo = []
        for r in records:
            if r['source_id'] in existing:
                continue
            root, sub, l3 = r['path']
            try:
                ids = (nodes[(root,)], nodes[(root, sub)], nodes[(root, sub, l3)] if l3 else None)
            except KeyError as e:
                raise CommandError(f'Question {r["source_id"]}: category {e} not found, run seed_taxonomy first.')
            todo.append((r, ids))

        self.stdout.write(f'{len(records)} in file, {len(existing)} already imported, {len(todo)} to create.')
        if dry_run or not todo:
            return

        created = 0
        for start in range(0, len(todo), CHUNK):
            with transaction.atomic():
                created += self.create_chunk(todo[start:start + CHUNK], sections, topics)
            self.stdout.write(f'  {created}/{len(todo)}')
        self.stdout.write(self.style.SUCCESS(f'Imported {created} questions.'))

    @staticmethod
    def category_lookup():
        by_id = {c.id: c for c in Category.objects.all()}
        nodes = {}
        for c in by_id.values():
            names, node = [], c
            while node:
                names.insert(0, node.name)
                node = by_id.get(node.parent_id)
            nodes[tuple(names)] = c.id
        return nodes

    @staticmethod
    def create_chunk(chunk, sections, topics):
        questions = []
        for r, (root_id, sub_id, l3_id) in chunk:
            problems = r.get('problems') or []
            usable = r['correct'] is not None and len(r['options']) >= 2 and not any(
                p.startswith(('The question image', 'Empty question', 'More than one', 'No correct', 'The marked', 'Fewer than'))
                for p in problems
            )
            questions.append(Question(
                source_id=r['source_id'],
                text_question=r['text'],
                notes=r.get('explanation'),
                hint=r.get('hint'),
                show_answer_explanation=bool(r.get('explanation')),
                question_type=Question.QUESTION_TYPE_QUESTION,
                answer_type=Question.ANSWER_TYPE_RADIO,
                category_id=root_id,
                sub_category_id=sub_id,
                sub_subcategory_id=l3_id,
                exam_year=r.get('exam_year'),
                keep_answer_order=bool(r.get('fixed_order')),
                status=Question.ACTIVE if usable and r.get('active_before', True) else Question.INACTIVE,
                needs_review=bool(problems),
                review_note='\n'.join(problems) or None,
            ))
        Question.objects.bulk_create(questions)  # PostgreSQL sets the ids

        answers, owners = [], []
        for q, (r, _) in zip(questions, chunk):
            for i, option in enumerate(r['options']):
                answers.append(Answer(question_id=q.id, answer_option=option))
                owners.append((q, i == r['correct']))
        Answer.objects.bulk_create(answers)
        for answer, (q, is_correct) in zip(answers, owners):
            if is_correct:
                q.correct_answer_id = answer.id
        Question.objects.bulk_update([q for q in questions if q.correct_answer_id], ['correct_answer'])

        links, topic_links = [], []
        for q, (r, _) in zip(questions, chunk):
            section_id = sections.get(r.get('section'))
            if section_id:
                links.append(ExamSectionLink(question_id=q.id, section_id=section_id))
                topic_id = topics.get((section_id, r.get('topic')))
                if topic_id:
                    topic_links.append(QuestionTopic(question_id=q.id, topic_id=topic_id))
        ExamSectionLink.objects.bulk_create(links)
        QuestionTopic.objects.bulk_create(topic_links)
        return len(questions)
