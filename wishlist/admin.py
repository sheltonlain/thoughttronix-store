from django.contrib import admin

from .models import Wishlist, WishlistItem


class WishlistItemInline(admin.TabularInline):
    model = WishlistItem
    extra = 0


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("user", "item_count")
    search_fields = ("user__username",)
    inlines = [WishlistItemInline]

    @admin.display(description="Items")
    def item_count(self, wishlist):
        return wishlist.items.count()
