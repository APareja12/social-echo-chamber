from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone
from datetime import timedelta

class Room(models.Model):
    """Main room model where users collaborate on music"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    is_public = models.BooleanField(default=True)
    max_users = models.IntegerField(default=8)
    room_color = models.CharField(max_length=7, default='#6366f1')  # Hex color for theme
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def active_member_count(self):
        """Return count of currently active members"""
        return self.members.filter(is_active=True).count()
    
    @property
    def is_full(self):
        """Check if room is at capacity"""
        return self.active_member_count >= self.max_users

class RoomMember(models.Model):
    """Users who have joined a room"""
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # 3D position in the room
    position_x = models.FloatField(default=0.0)  # -5.0 to 5.0
    position_y = models.FloatField(default=0.0)  # -2.0 to 2.0  
    position_z = models.FloatField(default=0.0)  # -5.0 to 5.0
    
    # Visual customization
    avatar_color = models.CharField(max_length=7, default='#f59e0b')
    username_override = models.CharField(max_length=50, blank=True)  # Custom display name
    
    # Permissions
    is_moderator = models.BooleanField(default=False)
    can_control_music = models.BooleanField(default=True)
    can_send_waves = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('room', 'user')
        ordering = ['joined_at']
    
    def __str__(self):
        return f"{self.display_name} in {self.room.name}"
    
    @property
    def display_name(self):
        """Return custom name or username"""
        return self.username_override or self.user.username
    
    def update_position(self, x, y, z):
        """Update 3D position with bounds checking"""
        self.position_x = max(-5.0, min(5.0, x))
        self.position_y = max(-2.0, min(2.0, y))
        self.position_z = max(-5.0, min(5.0, z))
        self.save()

class Song(models.Model):
    """Individual songs that can be added to playlists"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    artist = models.CharField(max_length=200)
    album = models.CharField(max_length=200, blank=True)
    duration = models.IntegerField()  # Duration in seconds
    
    # External service IDs
    spotify_id = models.CharField(max_length=100, blank=True)
    youtube_id = models.CharField(max_length=100, blank=True)
    apple_music_id = models.CharField(max_length=100, blank=True)
    
    # File storage (for uploaded files)
    file_url = models.URLField(blank=True)
    preview_url = models.URLField(blank=True)  # 30-second preview
    
    # Metadata
    genre = models.CharField(max_length=50, default='Unknown')
    year = models.IntegerField(null=True, blank=True)
    bpm = models.IntegerField(null=True, blank=True)  # Beats per minute
    energy = models.FloatField(null=True, blank=True)  # 0.0 to 1.0
    valence = models.FloatField(null=True, blank=True)  # 0.0 to 1.0 (mood)
    
    # Tracking
    added_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    play_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.artist}"
    
    @property
    def duration_formatted(self):
        """Return duration as MM:SS format"""
        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes}:{seconds:02d}"
    
    def increment_play_count(self):
        """Increment play count atomically"""
        self.play_count = models.F('play_count') + 1
        self.save(update_fields=['play_count'])

class Playlist(models.Model):
    """Room's music playlist and playback state"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.OneToOneField(Room, on_delete=models.CASCADE, related_name='playlist')
    
    # Current playback state
    current_song = models.ForeignKey(Song, on_delete=models.SET_NULL, null=True, blank=True)
    current_position = models.IntegerField(default=0)  # Seconds into current song
    is_playing = models.BooleanField(default=False)
    is_shuffled = models.BooleanField(default=False)
    repeat_mode = models.CharField(max_length=10, choices=[
        ('off', 'Off'),
        ('one', 'Repeat One'),
        ('all', 'Repeat All'),
    ], default='off')
    
    # Playback control
    volume = models.FloatField(default=0.8)  # 0.0 to 1.0
    last_updated = models.DateTimeField(auto_now=True)
    last_played_at = models.DateTimeField(null=True, blank=True)
    
    # Auto-management
    auto_skip_enabled = models.BooleanField(default=True)
    auto_add_similar = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-last_updated']
    
    def __str__(self):
        return f"Playlist for {self.room.name}"
    
    @property
    def total_duration(self):
        """Total duration of all songs in playlist"""
        return self.songs.aggregate(
            total=models.Sum('song__duration')
        )['total'] or 0
    
    @property
    def song_count(self):
        """Number of songs in playlist"""
        return self.songs.count()
    
    def play(self):
        """Start playback"""
        self.is_playing = True
        self.last_played_at = timezone.now()
        self.save()
    
    def pause(self):
        """Pause playback"""
        self.is_playing = False
        self.save()
    
    def next_song(self):
        """Get next song in playlist"""
        if not self.current_song:
            first_song = self.songs.first()
            return first_song.song if first_song else None
        
        current_playlist_song = self.songs.filter(song=self.current_song).first()
        current_order = current_playlist_song.order if current_playlist_song else None
        if current_order is not None:
            next_song = self.songs.filter(order__gt=current_order).first()
            if next_song:
                return next_song.song
            elif self.repeat_mode == 'all':
                first_song = self.songs.first()
                return first_song.song if first_song else None
        return None

class PlaylistSong(models.Model):
    """Songs in a playlist with order and metadata"""
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='songs')
    song = models.ForeignKey(Song, on_delete=models.CASCADE)
    order = models.IntegerField()
    
    # Tracking
    added_by = models.ForeignKey(User, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    
    # Voting system
    upvotes = models.IntegerField(default=0)
    downvotes = models.IntegerField(default=0)
    
    # Metadata
    notes = models.TextField(blank=True)  # User notes about the song
    
    class Meta:
        ordering = ['order']
        unique_together = ('playlist', 'order')
    
    def __str__(self):
        return f"{self.song.title} in {self.playlist.room.name}"
    
    @property
    def vote_score(self):
        """Net vote score (upvotes - downvotes)"""
        return self.upvotes - self.downvotes

class SoundWave(models.Model):
    """Visual sound waves sent between users"""
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='sound_waves')
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_waves')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_waves')
    
    # Visual properties
    intensity = models.FloatField(default=1.0)  # 0.0 to 2.0
    color = models.CharField(max_length=7, default='#3b82f6')  # Hex color
    wave_type = models.CharField(max_length=20, choices=[
        ('pulse', 'Pulse'),
        ('ring', 'Ring'),
        ('beam', 'Beam'),
        ('spiral', 'Spiral'),
    ], default='pulse')
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    # Optional message
    message = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Wave from {self.from_user.username} to {self.to_user.username}"
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            # Default expiration: 3 seconds from creation
            self.expires_at = timezone.now() + timedelta(seconds=3)
        super().save(*args, **kwargs)
    
    @classmethod
    def cleanup_expired(cls):
        """Remove expired sound waves"""
        cls.objects.filter(expires_at__lt=timezone.now()).delete()

class RoomActivity(models.Model):
    """Track room activity for analytics"""
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='activities')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    activity_type = models.CharField(max_length=30, choices=[
        ('user_joined', 'User Joined'),
        ('user_left', 'User Left'),
        ('song_added', 'Song Added'),
        ('song_played', 'Song Played'),
        ('song_skipped', 'Song Skipped'),
        ('wave_sent', 'Wave Sent'),
        ('position_changed', 'Position Changed'),
    ])
    
    # Optional related objects
    song = models.ForeignKey(Song, on_delete=models.SET_NULL, null=True, blank=True)
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='targeted_activities')
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)  # Additional data
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['room', 'timestamp']),
            models.Index(fields=['activity_type', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.activity_type} in {self.room.name} at {self.timestamp}"

class UserPreferences(models.Model):
    """User preferences for the application"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='echo_preferences')
    
    # Visual preferences
    default_avatar_color = models.CharField(max_length=7, default='#f59e0b')
    preferred_username = models.CharField(max_length=50, blank=True)
    
    # Audio preferences
    default_volume = models.FloatField(default=0.8)
    sound_effects_enabled = models.BooleanField(default=True)
    beat_visualization_enabled = models.BooleanField(default=True)
    
    # Privacy preferences
    show_listening_activity = models.BooleanField(default=True)
    allow_wave_messages = models.BooleanField(default=True)
    auto_join_public_rooms = models.BooleanField(default=False)
    
    # Notification preferences
    notify_on_room_invite = models.BooleanField(default=True)
    notify_on_song_add = models.BooleanField(default=True)
    notify_on_wave_received = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Preferences for {self.user.username}"

# Signal handlers for automatic cleanup and management
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_preferences(sender, instance, created, **kwargs):
    """Create user preferences when a new user is created"""
    if created:
        UserPreferences.objects.create(user=instance)

@receiver(post_save, sender=Room)
def create_room_playlist(sender, instance, created, **kwargs):
    """Create playlist when a new room is created"""
    if created:
        Playlist.objects.create(room=instance)

@receiver(pre_delete, sender=Room)
def cleanup_room_data(sender, instance, **kwargs):
    """Clean up related data when room is deleted"""
    # Clean up expired sound waves
    SoundWave.cleanup_expired()
    
    # Log room deletion
    RoomActivity.objects.create(
        room=instance,
        activity_type='room_deleted',
        metadata={'deleted_at': timezone.now().isoformat()}
    )