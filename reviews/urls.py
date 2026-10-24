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
]
