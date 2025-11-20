# urls.py
from django.urls import path, include
from . import views
from FlashAI.views import HomePageView
from django.contrib.auth.decorators import login_required

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path('create/', views.create_flashcard, name='create_flashcard'),
    path('list/', views.flashcard_list, name='flashcard_list'),
    path('add-category/', views.create_category, name="create_category"),
    path('upload-pdf/', views.upload_pdf, name='upload_pdf'),
    path('welcome/', views.welcome, name="welcome")
]
