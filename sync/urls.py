from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('settings/', views.settings, name='settings'),
    path('sync/run/', views.run_sync, name='run_sync'),
    path('sync/history/', views.sync_history, name='sync_history'),
]
