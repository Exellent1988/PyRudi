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
    path('<int:event_id>/update/', views.update_event, name='update_event'),
    path('<int:event_id>/invite-organizer/',
         views.invite_organizer, name='invite_organizer'),
    path('<int:event_id>/remove-organizer/<int:organizer_id>/',
         views.remove_organizer, name='remove_organizer'),
    path('<int:event_id>/team/<int:registration_id>/status/',
         views.update_team_status, name='update_team_status'),
    path('<int:event_id>/register/', views.register_team, name='register_team'),
    path('<int:event_id>/unregister/',
         views.unregister_team, name='unregister_team'),
    path('<int:event_id>/optimize/',
         views.start_optimization, name='start_optimization'),
    path('<int:event_id>/results/',
         views.optimization_results, name='optimization_results'),
    path('<int:event_id>/send-emails/',
         views.send_team_emails, name='send_team_emails'),
    path('<int:event_id>/assignment/<int:assignment_id>/adjust/',
         views.adjust_assignment, name='adjust_assignment'),
    path('<int:event_id>/route-geometry/',
         views.get_route_geometry, name='get_route_geometry'),
    path('<int:event_id>/optimization-progress/',
         views.get_optimization_progress, name='get_optimization_progress'),
    path('<int:event_id>/additional-optimization/',
         views.run_additional_optimization, name='run_additional_optimization'),

    # Afterparty Management URLs
    path('<int:event_id>/get-afterparty/',
         views.get_afterparty, name='get_afterparty'),
    path('<int:event_id>/save-afterparty/',
         views.save_afterparty, name='save_afterparty'),

    # Debug-URLs (nur für Development)
    path('<int:event_id>/debug-progress/',
         views.debug_progress, name='debug_progress'),
]
