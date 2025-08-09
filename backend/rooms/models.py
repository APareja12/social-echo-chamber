from django.db import models
from django.contrib.auth.models import User
import uuid

class Room(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    is_public = models.BooleanField(default=True)
    max_users = models.IntegerField(default=8)
    room_color = models.CharField(max_length=7, default='#6366f1')  # Hex color
    
    def __str__(self):
        return self.name

class RoomMember(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    avatar_color = models.CharField(max_length=7, default='#f59e0b')
    position_x = models.FloatField(default=0)  # 3D position in room
    position_y = models.FloatField(default=0)
    position_z = models.FloatField(default=0)
    
    class Meta:
        unique_together = ('room', 'user')

class Song(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    artist = models.CharField(max_length=200)
    duration = models.IntegerField()  # in seconds
    file_url = models.URLField(blank=True)  # For demo purposes
    spotify_id = models.CharField(max_length=100, blank=True)
    added_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} - {self.artist}"

class Playlist(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.OneToOneField(Room, on_delete=models.CASCADE, related_name='playlist')
    current_song = models.ForeignKey(Song, on_delete=models.SET_NULL, null=True, blank=True)
    current_position = models.IntegerField(default=0)  # seconds into current song
    is_playing = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)

class PlaylistSong(models.Model):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='songs')
    song = models.ForeignKey(Song, on_delete=models.CASCADE)
    order = models.IntegerField()
    added_by = models.ForeignKey(User, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order']

class SoundWave(models.Model):
    """Represents visual sound waves between users"""
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='sound_waves')
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_waves')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_waves')
    intensity = models.FloatField(default=1.0)  # Wave strength
    color = models.CharField(max_length=7, default='#3b82f6')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
