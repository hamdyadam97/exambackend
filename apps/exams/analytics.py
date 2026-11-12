"""Result analytics for one exam attempt, computed only from what was recorded.

Scoring (equal-weight questions, no negative marking — the system's current grading):
  answered   = correct + wrong            unanswered = total - answered
  score      = correct / total x 100      accuracy   = correct / answered x 100 (None when nothing answered)
  completion = answered / total x 100
Per-question time exists only for attempts recorded after `ExamTrialDetail.time_spent_seconds` was added;
older attempts report `has_question_timing = False` and no per-question figures (never estimates).
"""
from collections import OrderedDict

from apps.content.models import Setting

LEVELS = (('excellent', 'exam_level_excellent', 85), ('very_good', 'exam_level_very_good', 75))
DEFAULT_TARGET_SECONDS = 90


def _int_setting(key, default):
    try:
        return int(Setting.value_of(key, default))
    except (TypeError, ValueError):
        return default


def pct(part, whole):
    return round(part * 100 / whole, 1) if whole else None


def signature(trail):
    """Attempts of "the same exam" share the categories they were built from."""
    return (
        tuple(sorted(trail.categories.values_list('id', flat=True))),
        tuple(sorted(trail.sub_categories.values_list('id', flat=True))),
        tuple(sorted(trail.sub_sub_categories.values_list('id', flat=True))),
    )


def _status(detail):
    if not detail.answer_id:
        return 'unanswered'
    return 'correct' if detail.is_correct else 'wrong'


def _group(rows, key):
    groups = OrderedDict()
    for row in rows:
        for name in key(row):
            if name:
                groups.setdefault(name, []).append(row)
    out = []
    for name, items in groups.items():
        correct = sum(1 for r in items if r['status'] == 'correct')
        wrong = sum(1 for r in items if r['status'] == 'wrong')
        timed = [r['seconds'] for r in items if r['seconds'] is not None]
        out.append({
            'name': name,
            'total': len(items),
            'correct': correct,
            'wrong': wrong,
            'unanswered': len(items) - correct - wrong,
            'accuracy': pct(correct, correct + wrong),
            'avg_seconds': round(sum(timed) / len(timed)) if timed else None,
            'questions': [r['number'] for r in items],
        })
    return out


def build(trail, student_name=''):
    from apps.exams.models import ExamSectionLink, QuestionTopic

    details = list(trail.details.select_related(
        'question__category', 'question__sub_category', 'question__sub_subcategory',
    ).order_by('id'))
    qids = [d.question_id for d in details]
    sections, topics = {}, {}
    for qid, name in ExamSectionLink.objects.filter(question_id__in=qids).values_list('question_id', 'section__name'):
        sections.setdefault(qid, []).append(name)
    for qid, name in QuestionTopic.objects.filter(question_id__in=qids).values_list('question_id', 'topic__topic'):
        topics.setdefault(qid, []).append(name)

    from apps.exams.models import SavedQuestion
    saved = set(SavedQuestion.objects.filter(user_id=trail.user_id, question_id__in=qids).values_list('question_id', flat=True))

    rows = []
    for number, d in enumerate(details, 1):
        q = d.question
        subject = (q.sub_subcategory or q.sub_category or q.category)
        rows.append({
            'number': number,
            'question_id': d.question_id,
            'answer_id': d.answer_id,
            'status': _status(d),
            'seconds': d.time_spent_seconds,
            'marked': bool(d.is_review or d.is_marked),
            'saved': d.question_id in saved,
            'subject': subject.name if subject else None,
            'sections': sections.get(d.question_id, []),
            'topics': topics.get(d.question_id, []),
        })

    total = len(rows)
    correct = sum(1 for r in rows if r['status'] == 'correct')
    wrong = sum(1 for r in rows if r['status'] == 'wrong')
    answered = correct + wrong
    score = pct(correct, total) or 0

    pass_mark = _int_setting('exam_pass_mark', 60)
    thresholds = {key: _int_setting(setting, default) for key, setting, default in LEVELS}
    if score >= thresholds['excellent']:
        level = 'excellent'
    elif score >= thresholds['very_good']:
        level = 'very_good'
    elif score >= pass_mark:
        level = 'good'
    else:
        level = 'needs_improvement'

    # Time
    elapsed = None
    if trail.created_at and trail.updated_at and trail.status == 'completed':
        elapsed = max(0, int((trail.updated_at - trail.created_at).total_seconds()))
        if trail.duration_minutes:
            elapsed = min(elapsed, trail.duration_minutes * 60)
    limit = trail.duration_minutes * 60 if trail.duration_minutes else None
    timed_rows = [r for r in rows if r['seconds'] is not None]
    answered_timed = [r for r in timed_rows if r['status'] != 'unanswered']
    target = round(limit / total) if limit and total else _int_setting('exam_target_seconds_per_question', DEFAULT_TARGET_SECONDS)

    def avg(items):
        return round(sum(r['seconds'] for r in items) / len(items)) if items else None

    quadrants = None
    if answered_timed:
        quadrants = {
            'fast_correct': sum(1 for r in answered_timed if r['seconds'] <= target and r['status'] == 'correct'),
            'fast_wrong': sum(1 for r in answered_timed if r['seconds'] <= target and r['status'] == 'wrong'),
            'slow_correct': sum(1 for r in answered_timed if r['seconds'] > target and r['status'] == 'correct'),
            'slow_wrong': sum(1 for r in answered_timed if r['seconds'] > target and r['status'] == 'wrong'),
        }
    fastest = min(answered_timed, key=lambda r: r['seconds']) if answered_timed else None
    slowest = max(answered_timed, key=lambda r: r['seconds']) if answered_timed else None

    # Previous attempts of the same exam (same categories), oldest first.
    from apps.exams.models import ExamTrail
    sig = signature(trail)
    attempts = []
    for other in ExamTrail.objects.filter(user_id=trail.user_id, status='completed').order_by('created_at', 'id'):
        if other.id != trail.id and signature(other) != sig:
            continue
        o_total = other.total_questions or 0
        o_answered = (other.correct_answers or 0) + (other.wrong_answers or 0)
        o_timed = list(other.details.filter(time_spent_seconds__isnull=False, answer__isnull=False)
                       .values_list('time_spent_seconds', flat=True))
        attempts.append({
            'id': other.id,
            'date': other.created_at,
            'score': pct(other.correct_answers or 0, o_total) or 0,
            'accuracy': pct(other.correct_answers or 0, o_answered),
            'wrong': other.wrong_answers or 0,
            'total': o_total,
            'avg_seconds': round(sum(o_timed) / len(o_timed)) if o_timed else None,
            'difficulty': other.difficulty,
            'current': other.id == trail.id,
        })
    attempt_number = next((i for i, a in enumerate(attempts, 1) if a['current']), len(attempts) or 1)

    path = [c.name for c in (trail.categories.first(), trail.sub_categories.first(), trail.sub_sub_categories.first()) if c]

    return {
        'exam': {
            'id': trail.id,
            'title': trail.title,
            'path': path,
            'student': student_name,
            'date': trail.created_at,
            'submitted_at': trail.updated_at if trail.status == 'completed' else None,
            'status': trail.status,
            'mode': trail.mode,
            'attempt_number': attempt_number,
            'can_review': trail.reveals_answers(),
            'timed': bool(trail.duration_minutes),
        },
        'summary': {
            'total': total,
            'correct': correct,
            'wrong': wrong,
            'unanswered': total - answered,
            'answered': answered,
            'score': score,
            'accuracy': pct(correct, answered),
            'completion': pct(answered, total) or 0,
            'pass_mark': pass_mark,
            'passed': score >= pass_mark,
            'level': level,
            'thresholds': {**thresholds, 'good': pass_mark},
        },
        'time': {
            'limit_seconds': limit,
            'elapsed_seconds': elapsed,
            'remaining_seconds': max(limit - elapsed, 0) if limit is not None and elapsed is not None else None,
            'has_question_timing': bool(timed_rows),
            'target_seconds': target,
            'avg_answered_seconds': avg(answered_timed),
            'avg_correct_seconds': avg([r for r in answered_timed if r['status'] == 'correct']),
            'avg_wrong_seconds': avg([r for r in answered_timed if r['status'] == 'wrong']),
            'fastest': {'number': fastest['number'], 'seconds': fastest['seconds']} if fastest else None,
            'slowest': {'number': slowest['number'], 'seconds': slowest['seconds']} if slowest else None,
            'quadrants': quadrants,
        },
        'questions': rows,
        'breakdown': {
            'subjects': _group(rows, lambda r: [r['subject']]),
            'sections': _group(rows, lambda r: r['sections']),
            'topics': _group(rows, lambda r: r['topics']),
        },
        'attempts': attempts,
    }
