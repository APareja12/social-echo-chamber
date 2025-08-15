#!/usr/bin/env python3
"""
WebSocket Server for Social Echo Chamber
Handles real-time communication between users in 3D rooms
"""

from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
CORS(app, origins=["http://localhost:8000", "http://127.0.0.1:8000"])

socketio = SocketIO(app, cors_allowed_origins="*")

# Store connected users and room data
connected_users = {}
room_data = {}

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'message': 'Connected to Echo Chamber server'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")
    
    # Clean up user data
    if request.sid in connected_users:
        user_data = connected_users[request.sid]
        room_id = user_data.get('room_id')
        
        if room_id and room_id in room_data:
            # Remove user from room
            room_data[room_id]['users'].pop(request.sid, None)
            
            # Notify other users in room
            emit('user_left', {
                'user_id': user_data.get('user_id'),
                'username': user_data.get('username')
            }, room=room_id)
            
            logger.info(f"User {user_data.get('username')} left room {room_id}")
        
        del connected_users[request.sid]

@socketio.on('join_room')
def handle_join_room(data):
    """Handle user joining a room"""
    try:
        room_id = data.get('room_id')
        user_id = data.get('user_id')
        username = data.get('username')
        avatar_color = data.get('avatar_color', '#3b82f6')
        
        if not all([room_id, user_id, username]):
            emit('error', {'message': 'Missing required fields'})
            return
        
        # Store user data
        connected_users[request.sid] = {
            'room_id': room_id,
            'user_id': user_id,
            'username': username,
            'avatar_color': avatar_color,
            'position': data.get('position', {'x': 0, 'y': 0, 'z': 0})
        }
        
        # Initialize room if doesn't exist
        if room_id not in room_data:
            room_data[room_id] = {
                'users': {},
                'current_song': None,
                'playback_position': 0
            }
        
        # Add user to room
        join_room(room_id)
        room_data[room_id]['users'][request.sid] = connected_users[request.sid]
        
        # Notify user of successful join
        emit('room_joined', {
            'room_id': room_id,
            'users': [user for user in room_data[room_id]['users'].values()],
            'current_song': room_data[room_id]['current_song'],
            'playback_position': room_data[room_id]['playback_position']
        })
        
        # Notify other users
        emit('user_joined', {
            'user_id': user_id,
            'username': username,
            'avatar_color': avatar_color,
            'position': connected_users[request.sid]['position']
        }, room=room_id, include_self=False)
        
        logger.info(f"User {username} joined room {room_id}")
        
    except Exception as e:
        logger.error(f"Error joining room: {e}")
        emit('error', {'message': 'Failed to join room'})

@socketio.on('leave_room')
def handle_leave_room(data):
    """Handle user leaving a room"""
    try:
        if request.sid in connected_users:
            user_data = connected_users[request.sid]
            room_id = user_data.get('room_id')
            
            if room_id:
                leave_room(room_id)
                
                if room_id in room_data:
                    room_data[room_id]['users'].pop(request.sid, None)
                
                emit('user_left', {
                    'user_id': user_data.get('user_id'),
                    'username': user_data.get('username')
                }, room=room_id)
                
                logger.info(f"User {user_data.get('username')} left room {room_id}")
            
            # Clear user data
            connected_users[request.sid]['room_id'] = None
            
    except Exception as e:
        logger.error(f"Error leaving room: {e}")

@socketio.on('update_position')
def handle_update_position(data):
    """Handle user position updates"""
    try:
        if request.sid in connected_users:
            user_data = connected_users[request.sid]
            room_id = user_data.get('room_id')
            
            # Update position
            new_position = data.get('position', {})
            user_data['position'] = new_position
            
            if room_id and room_id in room_data:
                room_data[room_id]['users'][request.sid]['position'] = new_position
                
                # Broadcast position update
                emit('position_updated', {
                    'user_id': user_data.get('user_id'),
                    'position': new_position
                }, room=room_id, include_self=False)
        
    except Exception as e:
        logger.error(f"Error updating position: {e}")

@socketio.on('send_sound_wave')
def handle_send_sound_wave(data):
    """Handle sound wave transmission between users"""
    try:
        if request.sid in connected_users:
            user_data = connected_users[request.sid]
            room_id = user_data.get('room_id')
            
            if room_id:
                wave_data = {
                    'from_user_id': user_data.get('user_id'),
                    'to_user_id': data.get('to_user_id'),
                    'color': data.get('color', '#3b82f6'),
                    'intensity': data.get('intensity', 1.0),
                    'timestamp': datetime.now().isoformat()
                }
                
                emit('sound_wave_received', wave_data, room=room_id)
                logger.info(f"Sound wave sent from {user_data.get('user_id')} to {data.get('to_user_id')}")
        
    except Exception as e:
        logger.error(f"Error sending sound wave: {e}")

@socketio.on('music_control')
def handle_music_control(data):
    """Handle music playback controls"""
    try:
        if request.sid in connected_users:
            user_data = connected_users[request.sid]
            room_id = user_data.get('room_id')
            
            if room_id and room_id in room_data:
                action = data.get('action')
                
                if action == 'play_pause':
                    emit('music_play_pause', {
                        'user_id': user_data.get('user_id')
                    }, room=room_id)
                
                elif action == 'skip':
                    emit('music_skip', {
                        'user_id': user_data.get('user_id')
                    }, room=room_id)
                
                elif action == 'update_song':
                    song_data = data.get('song_data')
                    if song_data:
                        room_data[room_id]['current_song'] = song_data
                        room_data[room_id]['playback_position'] = 0
                        
                        emit('song_updated', {
                            'song_data': song_data,
                            'user_id': user_data.get('user_id')
                        }, room=room_id)
                
                logger.info(f"Music control: {action} by {user_data.get('user_id')} in room {room_id}")
        
    except Exception as e:
        logger.error(f"Error handling music control: {e}")

@socketio.on('sync_playback')
def handle_sync_playback(data):
    """Handle playback synchronization"""
    try:
        if request.sid in connected_users:
            user_data = connected_users[request.sid]
            room_id = user_data.get('room_id')
            
            if room_id and room_id in room_data:
                position = data.get('position', 0)
                room_data[room_id]['playback_position'] = position
                
                emit('playback_synced', {
                    'position': position,
                    'timestamp': datetime.now().isoformat()
                }, room=room_id, include_self=False)
        
    except Exception as e:
        logger.error(f"Error syncing playback: {e}")

if __name__ == '__main__':
    try:
        logger.info("Starting Echo Chamber WebSocket Server...")
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")