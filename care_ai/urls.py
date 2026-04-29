from django.http import JsonResponse
from django.urls import path

from care_ai.api.viewsets import AskAPIView


def ping(request):
    return JsonResponse({"status": "OK", "plugin": "care_ai"})


urlpatterns = [
    path("ping/", ping, name="care-ai-ping"),
    path(
        "encounter/<uuid:encounter_external_id>/ask/",
        AskAPIView.as_view(),
        name="care-ai-ask",
    ),
]
