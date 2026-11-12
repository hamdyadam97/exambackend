"""Which questions a user may practise: the categories of their active subscriptions.

A package is linked to one category at any level. Subscribing opens every question under it:
  level 1 (e.g. "SMLE - Prometric")            -> all its questions
  level 2 (e.g. "Residency and Board > Urology") -> only that sub-category
  level 3                                        -> only that subject
Staff accounts see everything (to test the bank).
"""
from dataclasses import dataclass, field

from django.db.models import Q


@dataclass
class AccessScope:
    everything: bool = False
    roots: set = field(default_factory=set)    # level-1 ids fully open
    subs: set = field(default_factory=set)     # level-2 ids fully open
    leaves: set = field(default_factory=set)   # level-3 ids open
    visible: set = field(default_factory=set)  # every category to list in the exam builder

    def question_q(self, prefix=''):
        """Q on Question (through `prefix`, e.g. 'questions_as_sub') for the open questions."""
        if self.everything:
            return Q()
        p = f'{prefix}__' if prefix else ''
        q = Q(**{f'{p}pk__in': []})
        if self.roots:
            q |= Q(**{f'{p}category_id__in': self.roots})
        if self.subs:
            q |= Q(**{f'{p}sub_category_id__in': self.subs})
        if self.leaves:
            q |= Q(**{f'{p}sub_subcategory_id__in': self.leaves})
        return q


def access_scope(user):
    if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
        return AccessScope(everything=True)
    if not getattr(user, 'is_authenticated', False):
        return AccessScope()

    from apps.content.models import Category

    scope = AccessScope()
    categories = Category.objects.filter(
        packages__subscriptions__in=user.active_subscriptions(), packages__deleted_at__isnull=True,
    ).distinct()
    for c in categories:
        if c.level == Category.LEVEL_CATEGORY:
            scope.roots.add(c.id)
        elif c.level == Category.LEVEL_SUB_CATEGORY:
            scope.subs.add(c.id)
        else:
            scope.leaves.add(c.id)
        scope.visible.update(a.id for a in c.get_ancestors(include_self=True))
    if scope.roots or scope.subs:
        # Everything below an open category is visible too.
        scope.visible.update(Category.objects.filter(Q(parent_id__in=scope.roots | scope.subs)).values_list('id', flat=True))
        scope.visible.update(Category.objects.filter(parent__parent_id__in=scope.roots).values_list('id', flat=True))
    return scope
