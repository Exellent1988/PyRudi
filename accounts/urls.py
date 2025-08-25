from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'accounts'

# REST API Router
router = DefaultRouter()
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'teams', views.TeamViewSet, basename='team')

urlpatterns = [
    path('api/', include(router.urls)),

    # Web Views
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('team/create/', views.create_team, name='create_team'),
    path('team/<int:team_id>/', views.team_detail, name='team_detail'),

    # API Auth endpoints werden hier hinzugefügt
    # path('register/', views.RegisterView.as_view(), name='register'),
    # path('login/', views.LoginView.as_view(), name='login'),
    # path('logout/', views.LogoutView.as_view(), name='logout'),
]
