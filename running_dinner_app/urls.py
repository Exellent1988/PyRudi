"""
URL configuration for running_dinner_app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static


def health_check(request):
    """Health check endpoint für Docker"""
    return JsonResponse({
        'status': 'healthy',
        'service': 'running-dinner-app',
        'version': '1.0.0'
    })


def home_view(request):
    """Home-View mit Template"""
    from django.shortcuts import render
    from events.models import Event

    # Hole die nächsten 3 öffentlichen Events
    upcoming_events = Event.objects.filter(
        is_public=True,
        status__in=['planning', 'registration_open', 'registration_closed']
    ).order_by('event_date')[:3]

    context = {
        'upcoming_events': upcoming_events,
    }
    return render(request, 'home.html', context)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health_check'),

    # Auth URLs
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),

    # API URLs
    path('api/events/', include(('events.urls', 'events'), namespace='events_api')),
    path('api/accounts/', include(('accounts.urls',
         'accounts'), namespace='accounts_api')),

    # Web URLs
    path('events/', include('events.urls')),
    path('accounts/', include('accounts.urls')),
    # Navigation URLs in Admin verfügbar

    # Home
    path('', home_view, name='home'),
]

# Static and media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
