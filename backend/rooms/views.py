# rooms/views.py - Social Echo Chamber Django Views
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Count, Avg
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json
import random
import uuid

from .models import (
    Room, RoomMember, Song, Playlist, PlaylistSong, 
    SoundWave, RoomActivity, UserPreferences
)

# Home page view
def index(request):
    """Home page with room list"""
    # Get public rooms with member counts
    rooms = Room.objects.filter(is_public=True).annotate(
        member_count=Count('members', filter=models.Q(members__is_active=True))
    ).order_by('-created_at')[:10]
    
    context = {
        'rooms': rooms,
        'user': request.user if request.user.is_authenticated else None
    }
    return render(request, 'rooms/index.html', context)

# Room view
def room_view(request, room_id):
    """Main room interface"""
    room = get_object_or_404(Room, id=room_id)
    
    # Check if room is full
    if room.is_full and not room.members.filter(user=request.user).exists():
        return render(request, 'rooms/room_full.html', {'room': room})
    
    # Get or create user (for demo purposes, create anonymous users)
    if not request.user.is_authenticated:
        # Create temporary user for demo
        temp_username = f"Guest_{random.randint(1000, 9999)}"
        user, created = User.objects.get_or_create(
            username=temp_username,
            defaults={'first_name': 'Guest'}
        )
        login(request, user)
    else:
        user = request.user
    
    # Get or create room membership
    member, created = RoomMember.objects.get_or_create(
        room=room,
        user=user,
        defaults={
            'avatar_color': f"#{random.randint(0, 16777215):06x}",
            'position_x': random.uniform(-3, 3),
            'position_y': random.uniform(-1, 1),
            'position_z': random.uniform(-3, 3),
        }
    )
    
    # Update member as active
    member.is_active = True
    member.last_seen = timezone.now()
    member.save()
    
    # Get room playlist
    playlist = room.playlist
    
    # Log room join activity
    RoomActivity.objects.create(
        room=room,
        user=user,
        activity_type='user_joined'
    )
    
    context = {
        'room': room,
        'member': member,
        'playlist': playlist,
        'user_id': user.id,
        'websocket_url': 'ws://localhost:5000'  # Flask WebSocket server
    }
    return render(request, 'rooms/room.html', context)

# API Views
@api_view(['GET', 'POST'])
def api_rooms(request):
    """List rooms or create new room"""
    if request.method == 'GET':
        rooms = Room.objects.filter(is_public=True).annotate(
            member_count=Count('members', filter=models.Q(members__is_active=True))
        ).order_by('-created_at')
        
        rooms_data = []
        for room in rooms:
            rooms_data.append({
                'id': str(room.id),
                'name': room.name,
                'description': room.description,
                'member_count': room.member_count,
                'max_users': room.max_users,
                'room_color': room.room_color,
                'created_at': room.created_at.isoformat(),
                'is_full': room.member_count >= room.max_users
            })
        
        return Response(rooms_data)
    
    elif request.method == 'POST':
        data = request.data
        
        # Create user if not authenticated (for demo)
        if not request.user.is_authenticated:
            temp_username = f"Creator_{random.randint(1000, 9999)}"
            user, created = User.objects.get_or_create(
                username=temp_username,
                defaults={'first_name': 'Creator'}
            )
            login(request, user)
        else:
            user = request.user
        
        room = Room.objects.create(
            name=data.get('name', 'New Room'),
            description=data.get('description', ''),
            created_by=user,
            room_color=data.get('room_color', '#6366f1'),
            max_users=data.get('max_users', 8),
            is_public=data.get('is_public', True)
        )
        
        return Response({
            'id': str(room.id),
            'name': room.name,
            'message': 'Room created successfully'
        }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
def api_room_state(request, room_id):
    """Get current room state"""
    room = get_object_or_404(Room, id=room_id)
    
    # Get active members
    members = []
    for member in room.members.filter(is_active=True).select_related('user'):
        members.append({
            'user_id': member.user.id,
            'username': member.display_name,
            'avatar_color': member.avatar_color,
            'position': {
                'x': member.position_x,
                'y': member.position_y,
                'z': member.position_z
            },
            'is_moderator': member.is_moderator,
            'joined_at': member.joined_at.isoformat()
        })
    
    # Get playlist state
    playlist = room.playlist
    current_song = None
    if playlist.current_song:
        current_song = {
            'id': str(playlist.current_song.id),
            'title': playlist.current_song.title,
            'artist': playlist.current_song.artist,
            'album': playlist.current_song.album,
            'duration': playlist.current_song.duration,
            'genre': playlist.current_song.genre,
            'preview_url': playlist.current_song.preview_url
        }
    
    # Get recent sound waves (last 10 seconds)
    recent_waves = []
    cutoff_time = timezone.now() - timezone.timedelta(seconds=10)
    for wave in SoundWave.objects.filter(room=room, created_at__gte=cutoff_time):
        recent_waves.append({
            'from_user_id': wave.from_user.id,
            'to_user_id': wave.to_user.id,
            'intensity': wave.intensity,
            'color': wave.color,
            'wave_type': wave.wave_type,
            'created_at': wave.created_at.isoformat()
        })
    
    return Response({
        'room': {
            'id': str(room.id),
            'name': room.name,
            'description': room.description,
            'color': room.room_color,
            'member_count': len(members),
            'max_users': room.max_users
        },
        'members': members,
        'playlist': {
            'current_song': current_song,
            'position': playlist.current_position,
            'is_playing': playlist.is_playing,
            'volume': playlist.volume,
            'repeat_mode': playlist.repeat_mode,
            'is_shuffled': playlist.is_shuffled
        },
        'sound_waves': recent_waves
    })

@api_view(['POST'])
@csrf_exempt
def api_room_action(request, room_id):
    """Handle room actions like position updates, sound waves"""
    room = get_object_or_404(Room, id=room_id)
    
    if not request.user.is_authenticated:
        return Response({'error': 'Authentication required'}, 
                       status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        member = RoomMember.objects.get(room=room, user=request.user, is_active=True)
    except RoomMember.DoesNotExist:
        return Response({'error': 'Not a member of this room'}, 
                       status=status.HTTP_403_FORBIDDEN)
    
    action = request.data.get('action')
    
    if action == 'update_position':
        x = float(request.data.get('x', member.position_x))
        y = float(request.data.get('y', member.position_y))
        z = float(request.data.get('z', member.position_z))
        
        member.update_position(x, y, z)
        
        # Log activity
        RoomActivity.objects.create(
            room=room,
            user=request.user,
            activity_type='position_changed',
            metadata={'new_position': {'x': x, 'y': y, 'z': z}}
        )
        
        return Response({'status': 'position_updated'})
    
    elif action == 'send_wave':
        target_user_id = request.data.get('target_user_id')
        if not target_user_id:
            return Response({'error': 'target_user_id required'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        try:
            target_user = User.objects.get(id=target_user_id)
            target_member = RoomMember.objects.get(room=room, user=target_user, is_active=True)
        except (User.DoesNotExist, RoomMember.DoesNotExist):
            return Response({'error': 'Target user not found in room'}, 
                           status=status.HTTP_404_NOT_FOUND)
        
        # Create sound wave
        SoundWave.objects.create(
            room=room,
            from_user=request.user,
            to_user=target_user,
            intensity=float(request.data.get('intensity', 1.0)),
            color=request.data.get('color', '#3b82f6'),
            wave_type=request.data.get('wave_type', 'pulse'),
            message=request.data.get('message', '')
        )
        
        # Log activity
        RoomActivity.objects.create(
            room=room,
            user=request.user,
            activity_type='wave_sent',
            target_user=target_user
        )
        
        return Response({'status': 'wave_sent'})
    
    elif action == 'leave_room':
        member.is_active = False
        member.save()
        
        # Log activity
        RoomActivity.objects.create(
            room=room,
            user=request.user,
            activity_type='user_left'
        )
        
        return Response({'status': 'left_room'})
    
    else:
        return Response({'error': 'Unknown action'}, 
                       status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'POST'])
def api_room_songs(request, room_id):
    """Get room playlist or add songs"""
    room = get_object_or_404(Room, id=room_id)
    playlist = room.playlist
    
    if request.method == 'GET':
        songs = []
        for ps in playlist.songs.select_related('song', 'added_by').order_by('order'):
            songs.append({
                'id': str(ps.song.id),
                'title': ps.song.title,
                'artist': ps.song.artist,
                'album': ps.song.album,
                'duration': ps.song.duration,
                'genre': ps.song.genre,
                'order': ps.order,
                'added_by': ps.added_by.username,
                'added_at': ps.added_at.isoformat(),
                'upvotes': ps.upvotes,
                'downvotes': ps.downvotes,
                'vote_score': ps.vote_score
            })
        
        return Response({
            'playlist_id': str(playlist.id),
            'total_duration': playlist.total_duration,
            'song_count': playlist.song_count,
            'songs': songs
        })
    
    elif request.method == 'POST':
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, 
                           status=status.HTTP_401_UNAUTHORIZED)
        
        data = request.data
        
        # Create or get song
        song, created = Song.objects.get_or_create(
            title=data['title'],
            artist=data['artist'],
            defaults={
                'album': data.get('album', ''),
                'duration': int(data.get('duration', 180)),
                'genre': data.get('genre', 'Unknown'),
                'spotify_id': data.get('spotify_id', ''),
                'youtube_id': data.get('youtube_id', ''),
                'preview_url': data.get('preview_url', ''),
                'added_by': request.user
            }
        )
        
        # Add to playlist
        max_order = playlist.songs.aggregate(
            max_order=models.Max('order')
        )['max_order'] or 0
        
        playlist_song = PlaylistSong.objects.create(
            playlist=playlist,
            song=song,
            order=max_order + 1,
            added_by=request.user
        )
        
        # If this is the first song and nothing is playing, start playing
        if not playlist.current_song:
            playlist.current_song = song
            playlist.current_position = 0
            playlist.save()
        
        # Log activity
        RoomActivity.objects.create(
            room=room,
            user=request.user,
            activity_type='song_added',
            song=song
        )
        
        return Response({
            'id': str(song.id),
            'title': song.title,
            'artist': song.artist,
            'message': 'Song added to playlist'
        }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
def api_search_songs(request):
    """Search for songs"""
    query = request.GET.get('q', '')
    if not query:
        return Response({'error': 'Query parameter required'}, 
                       status=status.HTTP_400_BAD_REQUEST)
    
    # For demo, return some mock results
    # In production, integrate with Spotify/YouTube APIs
    demo_results = [
        {
            'id': str(uuid.uuid4()),
            'title': f'{query} Song {i+1}',
            'artist': f'Artist {i+1}',
            'album': f'Album {i+1}',
            'duration': 180 + i*10,
            'genre': ['Electronic', 'Rock', 'Pop', 'Jazz'][i % 4],
            'preview_url': f'https://demo.com/preview_{i+1}.mp3',
            'spotify_id': f'spotify_{i+1}',
            'youtube_id': f'youtube_{i+1}'
        }
        for i in range(min(10, len(query)))
    ]
    
    return Response(demo_results)

@api_view(['GET'])
def api_room_analytics(request, room_id):
    """Get room analytics"""
    room = get_object_or_404(Room, id=room_id)
    
    # Get activity stats
    total_activities = RoomActivity.objects.filter(room=room).count()
    
    # Genre distribution
    genre_stats = Song.objects.filter(
        playlistsong__playlist=room.playlist
    ).values('genre').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # User contributions
    user_stats = RoomActivity.objects.filter(
        room=room,
        activity_type='song_added'
    ).values('user__username').annotate(
        songs_added=Count('id')
    ).order_by('-songs_added')[:5]
    
    # Peak activity hours
    from django.db.models import Extract
    hour_stats = RoomActivity.objects.filter(room=room).extra(
        select={'hour': "strftime('%%H', timestamp)"}
    ).values('hour').annotate(
        activity_count=Count('id')
    ).order_by('-activity_count')[:5]
    
    return Response({
        'total_activities': total_activities,
        'genre_distribution': list(genre_stats),
        'top_contributors': list(user_stats),
        'peak_hours': list(hour_stats),
        'room_info': {
            'name': room.name,
            'created_at': room.created_at.isoformat(),
            'total_members': room.members.count(),
            'total_songs': room.playlist.song_count
        }
    })

# Error handlers
def handler404(request, exception):
    return render(request, 'rooms/404.html', status=404)

def handler500(request):
    return render(request, 'rooms/500.html', status=500)