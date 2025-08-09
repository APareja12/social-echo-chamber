from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta
import json
import random

@login_required
def room_view(request, room_id):
    room = get_object_or_404(Room, id=room_id)
    
    # Get or create room membership
    member, created = RoomMember.objects.get_or_create(
        room=room,
        user=request.user,
        defaults={
            'avatar_color': f"#{random.randint(0, 16777215):06x}",
            'position_x': random.uniform(-5, 5),
            'position_y': random.uniform(-2, 2),
            'position_z': random.uniform(-5, 5),
        }
    )
    
    # Get or create playlist
    playlist, created = Playlist.objects.get_or_create(room=room)
    
    context = {
        'room': room,
        'member': member,
        'playlist': playlist,
        'user_id': request.user.id,
    }
    return render(request, 'echo_chamber/room.html', context)

@csrf_exempt
@login_required
def api_room_state(request, room_id):
    room = get_object_or_404(Room, id=room_id)
    
    if request.method == 'GET':
        # Get current room state
        members = []
        for member in room.members.filter(is_active=True):
            members.append({
                'user_id': member.user.id,
                'username': member.user.username,
                'avatar_color': member.avatar_color,
                'position': {
                    'x': member.position_x,
                    'y': member.position_y,
                    'z': member.position_z
                }
            })
        
        # Get current playlist state
        playlist = room.playlist
        current_song = None
        if playlist.current_song:
            current_song = {
                'id': str(playlist.current_song.id),
                'title': playlist.current_song.title,
                'artist': playlist.current_song.artist,
                'duration': playlist.current_song.duration
            }
        
        return JsonResponse({
            'room': {
                'id': str(room.id),
                'name': room.name,
                'color': room.room_color
            },
            'members': members,
            'playlist': {
                'current_song': current_song,
                'position': playlist.current_position,
                'is_playing': playlist.is_playing
            },
            'sound_waves': get_active_sound_waves(room)
        })
    
    elif request.method == 'POST':
        data = json.loads(request.body)
        action = data.get('action')
        
        if action == 'update_position':
            member = RoomMember.objects.get(room=room, user=request.user)
            member.position_x = data.get('x', member.position_x)
            member.position_y = data.get('y', member.position_y)
            member.position_z = data.get('z', member.position_z)
            member.save()
            
        elif action == 'send_wave':
            target_user_id = data.get('target_user_id')
            if target_user_id:
                SoundWave.objects.create(
                    room=room,
                    from_user=request.user,
                    to_user_id=target_user_id,
                    intensity=data.get('intensity', 1.0),
                    color=data.get('color', '#3b82f6'),
                    expires_at=timezone.now() + timedelta(seconds=3)
                )
        
        return JsonResponse({'status': 'success'})

def get_active_sound_waves(room):
    """Get currently active sound waves in the room"""
    waves = SoundWave.objects.filter(
        room=room,
        expires_at__gt=timezone.now()
    ).select_related('from_user', 'to_user')
    
    wave_data = []
    for wave in waves:
        wave_data.append({
            'from_user_id': wave.from_user.id,
            'to_user_id': wave.to_user.id,
            'intensity': wave.intensity,
            'color': wave.color,
            'created_at': wave.created_at.isoformat()
        })
    
    return wave_data
