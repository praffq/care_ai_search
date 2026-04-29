from django.urls import path

from care_ai_search.api.viewsets import RunAIView

urlpatterns = [
    path("run/", RunAIView.as_view(), name="care_ai_search-run"),
]
