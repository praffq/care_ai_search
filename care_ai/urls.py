from django.urls import path

from care_ai.api.viewsets import RunAIView

urlpatterns = [
    path("run/", RunAIView.as_view(), name="care_ai-run"),
]
