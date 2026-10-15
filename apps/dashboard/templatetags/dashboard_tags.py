from collections import defaultdict
from django import template
from apps.dashboard.registry import DASHBOARD_MODELS
from apps.dashboard.arabic import to_arabic
from apps.dashboard.menu import get_menu_groups

register = template.Library()


@register.filter
def dashboard_attr(obj, field_name):
    """Return a friendly Arabic value for an object's field/method/property by name."""
    if obj is None or field_name is None:
        return '-'
    display_method = getattr(obj, f'get_{field_name}_display', None)
    if callable(display_method):
        return to_arabic(display_method())
    value = getattr(obj, field_name, None)
    if callable(value):
        value = value()
    if value is None:
        return '-'
    return to_arabic(value)


@register.filter
def field_verbose(model_meta, field_name):
    """Return the Arabic verbose name of a model field."""
    try:
        return to_arabic(model_meta.get_field(field_name).verbose_name)
    except Exception:
        return to_arabic(field_name)


@register.filter
def ar(value):
    return to_arabic(value)


@register.inclusion_tag('dashboard/menu.html', takes_context=True)
def dashboard_menu(context):
    groups = defaultdict(list)
    for section, config in DASHBOARD_MODELS.items():
        app = config['model']._meta.app_config.verbose_name or config['model']._meta.app_label
        groups[to_arabic(app)].append({
            'section': section,
            'verbose_name': to_arabic(config['verbose_name']),
        })
    return {
        'groups': dict(groups),
        'current_section': context.get('section'),
        'request': context.get('request'),
    }


@register.simple_tag(takes_context=True)
def admin_menu(context):
    """Return grouped, permission-filtered menu items."""
    request = context.get('request')
    if not request:
        return []
    return get_menu_groups(request)
