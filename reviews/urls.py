from django.urls import path

from . import views

app_name = "reviews"

# Mounted at the root, like orders and coupons: customer endpoints carry a
# reviews/ prefix here, and the back-office tab sits at backoffice/reviews/.
urlpatterns = [
    path(
        "reviews/product/<int:pk>/create/",
        views.CreateReviewView.as_view(),
        name="create",
    ),
    path("reviews/<int:pk>/edit/", views.EditReviewView.as_view(), name="edit"),
    path("reviews/<int:pk>/card/", views.ReviewCardView.as_view(), name="card"),
    path("reviews/<int:pk>/delete/", views.DeleteReviewView.as_view(), name="delete"),
    path(
        "backoffice/reviews/",
        views.ManageReviewListView.as_view(),
        name="manage_reviews",
    ),
    path(
        "backoffice/reviews/<int:pk>/delete/",
        views.ManageDeleteReviewView.as_view(),
        name="manage_delete",
    ),
]
