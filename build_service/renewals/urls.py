from django.urls import path

from . import views

urlpatterns = [
    path("health", views.HealthView.as_view()),
    path("samples", views.SampleListView.as_view()),
    path("samples/<slug:sample_id>/file", views.SampleFileView.as_view()),
    path("samples/<slug:sample_id>/extract", views.SampleExtractView.as_view()),
    path("extract", views.UploadExtractView.as_view()),
    path("requests", views.GenerateRequestsView.as_view()),
]
