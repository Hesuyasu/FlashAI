# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('create/', views.create_flashcard, name='create_flashcard'),
    path('list/', views.flashcard_list, name='flashcard_list'),
    path('add-category/', views.create_category, name="create_category"),
    path('upload-pdf/', views.upload_pdf, name='upload_pdf'),
]
