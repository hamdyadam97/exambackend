"""File questions into sections and topics by keywords (apps.exams.classify), and give a subject to
questions that have none. Only fills what is missing: questions already linked to a section, or
already given a subject, keep theirs (they may have been set by hand in the dashboard)."""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.content.models import Category, ExamSection, QuestionsTopic
from apps.exams.classify import classify, pick_subject, plain
from apps.exams.models import ExamSectionLink, Question, QuestionTopic

CHUNK = 2000


class Command(BaseCommand):
    help = 'File questions into sections/topics (and a missing subject) by keywords.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--show', type=int, default=0, help='Print N sample results.')

    def handle(self, dry_run=False, show=0, **options):
        sections = {s.name: s.id for s in ExamSection.objects.filter(category=None)}
        topics = {(t.section_id, t.topic): t.id for t in QuestionsTopic.objects.all()}
        leaves = {}
        for c in Category.objects.filter(level=Category.LEVEL_SUB_SUB_CATEGORY):
            leaves.setdefault(c.parent_id, {})[c.name] = c.id
        names = dict(Category.objects.values_list('id', 'name'))

        linked = set(ExamSectionLink.objects.values_list('question_id', flat=True))
        ids = list(Question.objects.exclude(id__in=linked).values_list('id', flat=True).order_by('id'))
        stats, subjects, shown = Counter(), Counter(), 0
        for start in range(0, len(ids), CHUNK):
            batch = Question.objects.filter(id__in=ids[start:start + CHUNK]).prefetch_related('answers')
            links, topic_links, subject_updates = [], [], []
            for q in batch:
                question = plain(q.text_question)
                extra = plain(' '.join(a.answer_option or '' for a in q.answers.all()), q.notes)
                path = [names.get(q.category_id, ''), names.get(q.sub_category_id, ''), names.get(q.sub_subcategory_id, '')]
                section, topic = classify(question, extra, path)
                stats[section] += 1
                links.append(ExamSectionLink(question_id=q.id, section_id=sections[section]))
                if topic:
                    stats['(with a topic)'] += 1
                    topic_links.append(QuestionTopic(question_id=q.id, topic_id=topics[(sections[section], topic)]))
                if not q.sub_subcategory_id and q.sub_category_id in leaves:
                    subject = pick_subject(question, section, list(leaves[q.sub_category_id]))
                    if subject:
                        q.sub_subcategory_id = leaves[q.sub_category_id][subject]
                        subject_updates.append(q)
                        subjects[f'{path[1]} > {subject}'] += 1
                if shown < show:
                    shown += 1
                    self.stdout.write(f'[{" > ".join(p for p in path if p)}] {section} / {topic} :: {question[:140]}')
            if not dry_run:
                with transaction.atomic():
                    ExamSectionLink.objects.bulk_create(links)
                    QuestionTopic.objects.bulk_create(topic_links)
                    Question.objects.bulk_update(subject_updates, ['sub_subcategory'])
        self.stdout.write(f'{len(ids)} questions without a section{" (dry run)" if dry_run else ""}.')
        for name, n in stats.most_common():
            self.stdout.write(f'  {n:6}  {name}')
        self.stdout.write('Subjects given:')
        for name, n in subjects.most_common():
            self.stdout.write(f'  {n:6}  {name}')
