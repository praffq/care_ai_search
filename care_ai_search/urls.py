from django.urls import path

from care_ai_search.api.viewsets import RunAIView

urlpatterns = [
    path("v1/run/", RunAIView.as_view(), name="care_ai_search-run"),
]
