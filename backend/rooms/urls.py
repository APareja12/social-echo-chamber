from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('room/<uuid:room_id>/', views.room_view, name='room'),
    path('api/room/<uuid:room_id>/state/', views.api_room_state, name='api_room_state'),
    path('api/rooms/', views.api_rooms, name='api_rooms'),
]