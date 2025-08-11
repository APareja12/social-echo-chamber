from django.urls import path
from . import views

app_name = 'rooms'

urlpatterns = [
    # Main pages
    path('', views.index, name='index'),
    path('room/<uuid:room_id>/', views.room_view, name='room'),
    
    # API endpoints
    path('api/rooms/', views.api_rooms, name='api_rooms'),
    path('api/room/<uuid:room_id>/state/', views.api_room_state, name='api_room_state'),
    path('api/room/<uuid:room_id>/action/', views.api_room_action, name='api_room_action'),
    path('api/room/<uuid:room_id>/songs/', views.api_room_songs, name='api_room_songs'),
    path('api/room/<uuid:room_id>/analytics/', views.api_room_analytics, name='api_room_analytics'),
    path('api/search/songs/', views.api_search_songs, name='api_search_songs'),
]