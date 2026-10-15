from django import template

register = template.Library()


@register.filter
def underscore_to_space(value: str) -> str:
    """Convert snake_case label into Title Case words."""
    if not value:
        return value
    return str(value).replace("_", " ").title()
