from django import template
from core.thumbnails import catalog_thumbnail

register = template.Library()
register.simple_tag(catalog_thumbnail)
