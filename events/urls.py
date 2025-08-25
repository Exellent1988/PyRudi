from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'events'

# REST API Router
router = DefaultRouter()
router.register(r'events', views.EventViewSet, basename='event')

urlpatterns = [
    path('api/', include(router.urls)),

    # Public Event URLs
    path('', views.event_list, name='event_list'),
    path('<int:event_id>/', views.event_detail, name='event_detail'),

    # Event Management URLs (Frontend statt Admin)
    path('organizer/dashboard/', views.organizer_dashboard,
         name='organizer_dashboard'),
    path('create/', views.create_event, name='create_event'),
    path('<int:event_id>/manage/', views.manage_event, name='manage_event'),
    path('<int:event_id>/invite-organizer/',
         views.invite_organizer, name='invite_organizer'),
    path('<int:event_id>/team/<int:registration_id>/status/',
         views.update_team_status, name='update_team_status'),
    path('<int:event_id>/register/', views.register_team, name='register_team'),
    path('<int:event_id>/unregister/', views.unregister_team, name='unregister_team'),
]
