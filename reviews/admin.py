from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "created_at", "edited_by_staff")
    list_filter = ("rating", "edited_by_staff")
    search_fields = ("product__name", "user__username", "comment")
    list_select_related = ("product", "user")
    date_hierarchy = "created_at"
