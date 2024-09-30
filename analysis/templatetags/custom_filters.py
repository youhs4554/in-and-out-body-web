from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    딕셔너리에서 주어진 key로 값을 반환하는 커스텀 필터.
    """
    return dictionary.get(key)

@register.filter
def split(value, delimiter=','):
    """Split a string by the given delimiter and return a list."""
    return value.split(delimiter)

@register.filter
def trim(value):
    """Remove leading and trailing whitespace from a string."""
    return value.strip() if value else value