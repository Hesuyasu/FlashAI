# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('create/', views.create_flashcard, name='create_flashcard'),
    path('flashcards/', views.flashcard_list, name='flashcard_list'),
    path('add-category/', views.create_category, name="create_category"),
    path('upload-pdf/', views.upload_pdf, name='upload_pdf'),
    path('<int:pk>/edit/', views.flashcard_update, name='flashcard_update'),
    path('<int:pk>/delete/', views.flashcard_delete, name='flashcard_delete'),
    path('flashcards/study/', views.study_flashcards, name='study_flashcards'),
    
]
