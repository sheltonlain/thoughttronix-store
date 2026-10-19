from django.urls import path

from . import views

app_name = "wishlist"

urlpatterns = [
    path("", views.WishlistView.as_view(), name="wishlist"),
    path("add/<int:pk>/", views.AddToWishlistView.as_view(), name="add"),
    path("remove/<int:pk>/", views.RemoveFromWishlistView.as_view(), name="remove"),
    path(
        "items/<int:pk>/remove/",
        views.RemoveWishlistItemView.as_view(),
        name="remove_item",
    ),
]
