"""
Per-student analytics for the dashboard, computed from the student's own exam answers.
"""
from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.content.models import QuestionsTopic
from apps.exams.models import Exam, ExamTrail, ExamTrialDetail, UserExam

PASS_SCORE = 50  # Same threshold the admin dashboard uses for its pass rate.
STRONG_ACCURACY = 75
WEAK_ACCURACY = 50
MIN_TOPIC_ANSWERS = 3  # Below this a topic's accuracy is too noisy to judge.


def _accuracy(correct, total):
    return round(correct * 100 / total) if total else 0


def _streak(active_days, today):
    """Consecutive days with answers, ending today (or yesterday if today has none yet)."""
    day = today if today in active_days else today - timedelta(days=1)
    streak = 0
    while day in active_days:
        streak += 1
        day -= timedelta(days=1)
    return streak


def student_insights(user):
    from apps.packages.models import Package
    from apps.packages.serializers import UserPackageResource

    today = timezone.localdate()
    # Only answers whose grading is already visible, so stats cannot leak results of an exam in progress.
    answered = ExamTrialDetail.objects.filter(
        Q(exam_trail__status='completed') | Q(exam_trail__mode=ExamTrail.MODE_TUTOR),
        exam_trail__user=user, answer__isnull=False,
    )

    completed = list(
        user.exam_trails.filter(status='completed', total_questions__gt=0).order_by('-updated_at')[:10]
    )[::-1]
    score_history = [
        {
            'date': trail.updated_at.date().isoformat(),
            'title': trail.title,
            'score': _accuracy(trail.correct_answers, trail.total_questions),
        }
        for trail in completed
    ]
    all_scores = [
        _accuracy(c, t) for c, t in user.exam_trails.filter(
            status='completed', total_questions__gt=0,
        ).values_list('correct_answers', 'total_questions')
    ]

    since = today - timedelta(days=6)
    per_day = {
        row['day']: row for row in answered.filter(updated_at__date__gte=since)
        .annotate(day=TruncDate('updated_at')).values('day')
        .annotate(correct=Count('id', filter=Q(is_correct=True)), wrong=Count('id', filter=Q(is_correct=False)))
    }
    daily_activity = []
    for i in range(7):
        day = since + timedelta(days=i)
        row = per_day.get(day, {})
        daily_activity.append({'date': day.isoformat(), 'correct': row.get('correct', 0), 'wrong': row.get('wrong', 0)})

    categories = [
        {
            'id': row['question__category_id'],
            'name': row['question__category__name'],
            'answered': row['total'],
            'accuracy': _accuracy(row['correct'], row['total']),
        }
        for row in answered.filter(question__category__isnull=False)
        .values('question__category_id', 'question__category__name')
        .annotate(total=Count('id'), correct=Count('id', filter=Q(is_correct=True)))
        .order_by('-total')
    ]

    topic_rows = [
        {
            'id': row['question__question_topics__topic_id'],
            'name': row['question__question_topics__topic__topic'],
            'answered': row['total'],
            'accuracy': _accuracy(row['correct'], row['total']),
        }
        for row in answered.filter(question__question_topics__topic__isnull=False)
        .values('question__question_topics__topic_id', 'question__question_topics__topic__topic')
        .annotate(total=Count('id'), correct=Count('id', filter=Q(is_correct=True)))
    ]
    judged = [t for t in topic_rows if t['answered'] >= MIN_TOPIC_ANSWERS]
    by_accuracy = sorted(judged, key=lambda t: t['accuracy'])

    subscribed_ids = list(user.subscribed_categories().values_list('id', flat=True)) + list(
        user.subscribed_sub_categories().values_list('id', flat=True)
    )
    practiced_topic_ids = {t['id'] for t in topic_rows}
    untouched_topics = [
        {'id': topic.id, 'name': topic.topic}
        for topic in QuestionsTopic.objects.filter(category_id__in=subscribed_ids)
        .exclude(id__in=practiced_topic_ids).order_by('topic')[:5]
    ]

    active_days = set(answered.annotate(day=TruncDate('updated_at')).values_list('day', flat=True).distinct())

    in_progress = user.exam_trails.exclude(status='completed').annotate(
        answered_count=Count('details', filter=Q(details__answer__isnull=False)),
    ).order_by('-updated_at').first()

    taken_exam_ids = UserExam.objects.filter(user=user).values_list('exam_id', flat=True)
    recommended_exams = [
        {'id': exam.id, 'title': exam.title, 'duration_minutes': exam.duration_minutes, 'category': exam.category.name if exam.category else None}
        for exam in Exam.objects.filter(
            status=Exam.ACTIVE, deleted_at__isnull=True, category_id__in=subscribed_ids,
        ).exclude(id__in=taken_exam_ids).select_related('category').order_by('-is_featured', 'order', '-created_at')[:3]
    ]

    current_sub = user.active_subscriptions().select_related('package').order_by('end_date').first()
    subscribed_package_ids = user.active_subscriptions().values_list('package_id', flat=True)
    offers = [
        {
            'id': pkg.id,
            'name': pkg.name,
            'price': float(pkg.price),
            'discount_percentage': pkg.discount_percentage,
            'category': pkg.category.name if pkg.category_id else None,
        }
        for pkg in Package.objects.filter(status=Package.ACTIVE, is_trial=False, deleted_at__isnull=True)
        .exclude(id__in=subscribed_package_ids).select_related('category')
        .order_by('-discount_percentage', '-is_featured', '-created_at')[:4]
    ]

    return {
        'score_history': score_history,
        'daily_activity': daily_activity,
        'categories': categories,
        'topics': {
            'strong': [t for t in reversed(by_accuracy) if t['accuracy'] >= STRONG_ACCURACY][:5],
            'needs_improvement': [t for t in by_accuracy if WEAK_ACCURACY <= t['accuracy'] < STRONG_ACCURACY][:5],
            'weak': [t for t in by_accuracy if t['accuracy'] < WEAK_ACCURACY][:5],
            'untouched': untouched_topics,
        },
        'achievements': {
            'passed_exams': sum(1 for s in all_scores if s >= PASS_SCORE),
            'perfect_scores': sum(1 for s in all_scores if s == 100),
            'active_days': len(active_days),
            'current_streak': _streak(active_days, today),
            'topics_practiced': len(topic_rows),
        },
        'wrong_questions': answered.filter(is_correct=False).values('question_id').distinct().count(),
        'in_progress': {
            'id': in_progress.id,
            'title': in_progress.title,
            'answered': in_progress.answered_count,
            'total': in_progress.question_count,
        } if in_progress else None,
        'recommended_exams': recommended_exams,
        'subscription': UserPackageResource(current_sub).data if current_sub else None,
        'offers': offers,
    }
