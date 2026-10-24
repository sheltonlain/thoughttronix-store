from django import template

register = template.Library()


@register.filter
def may_change(review, user):
    """``{% if review|may_change:user %}``: show Edit and Delete only to
    users permitted to change the review."""
    return review.may_change(user)


@register.inclusion_tag("reviews/partials/_stars.html")
def stars(value, size="sm"):
    """Read-only stars for a rating or an average, to the nearest whole star.

    No half stars: 4.5 shows five, 4.4 shows four.
    """
    # int(x + 0.5), not round(): round() goes to even, so 4.5 would be 4.
    filled = int(value + 0.5)
    return {"filled": filled, "size": size, "positions": range(1, 6)}
