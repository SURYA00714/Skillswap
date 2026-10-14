import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(128), primary_key=True)
    fullName = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=True)
    title = db.Column(db.String(255), nullable=True)
    specialization = db.Column(db.String(255), nullable=True)
    employmentType = db.Column(db.String(100), nullable=True)
    education = db.Column(db.String(255), nullable=True)
    qualifications = db.Column(db.String(255), nullable=True)
    skillLevel = db.Column(db.String(50), nullable=True)  # Beginner, Intermediate, Advanced, Expert
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    profilePhotoUrl = db.Column(db.Text, nullable=True)
    profileVisibility = db.Column(db.String(20), default='Public')
    
    offeredSkills = db.Column(db.JSON, default=list)
    wantedSkills = db.Column(db.JSON, default=list)
    availability = db.Column(db.JSON, default=list)
    
    rating = db.Column(db.Float, default=5.0)
    reviewCount = db.Column(db.Integer, default=0)
    onboarding_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.fullName or self.email.split('@')[0],
            'fullName': self.fullName or '',
            'email': self.email or '',
            'title': self.title or '',
            'specialization': self.specialization or '',
            'employmentType': self.employmentType or '',
            'education': self.education or '',
            'qualifications': self.qualifications or '',
            'skillLevel': self.skillLevel or 'Intermediate',
            'city': self.city or '',
            'state': self.state or '',
            'location': self.location or (f"{self.city}, {self.state}" if self.city and self.state else self.city or ''),
            'bio': self.bio or '',
            'photo_url': self.profilePhotoUrl or '/static/default-profile.png',
            'profilePhotoUrl': self.profilePhotoUrl or '/static/default-profile.png',
            'profileVisibility': self.profileVisibility or 'Public',
            'offeredSkill': self.offeredSkills or [],
            'requestedSkill': self.wantedSkills or [],
            'wantedSkill': self.wantedSkills or [],
            'availability': self.availability or 'Flexible',
            'rating': self.rating or 5.0,
            'reviewCount': self.reviewCount or 0,
            'onboarding_completed': self.onboarding_completed or False
        }


class Swap(db.Model):
    __tablename__ = 'swaps'

    id = db.Column(db.String(128), primary_key=True)
    swapId = db.Column(db.String(128), index=True, nullable=True)
    fromUserId = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=False, index=True)
    toUserId = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=False, index=True)
    offeredSkill = db.Column(db.String(255), nullable=True)
    requestedSkill = db.Column(db.String(255), nullable=True)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default='pending', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'swapId': self.swapId or self.id,
            'fromUserId': self.fromUserId,
            'toUserId': self.toUserId,
            'offeredSkill': self.offeredSkill,
            'requestedSkill': self.requestedSkill,
            'message': self.message,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.String(128), primary_key=True)
    senderId = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=False, index=True)
    receiverId = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=False, index=True)
    swapId = db.Column(db.String(128), nullable=True, index=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    isRead = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'senderId': self.senderId,
            'receiverId': self.receiverId,
            'swapId': self.swapId,
            'content': self.content,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'isRead': self.isRead
        }


class LearningSession(db.Model):
    __tablename__ = 'learning_sessions'

    id = db.Column(db.String(128), primary_key=True)
    swapId = db.Column(db.String(128), nullable=True, index=True)
    hostUserId = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=False)
    participantUserId = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    meetingUrl = db.Column(db.String(500), nullable=True)
    sessionDate = db.Column(db.Date, nullable=False)
    startTime = db.Column(db.Time, nullable=False)
    endTime = db.Column(db.Time, nullable=False)
    durationMinutes = db.Column(db.Integer, default=60)
    status = db.Column(db.String(50), default='scheduled', index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'swapId': self.swapId,
            'hostUserId': self.hostUserId,
            'participantUserId': self.participantUserId,
            'title': self.title,
            'description': self.description,
            'meetingUrl': self.meetingUrl,
            'sessionDate': self.sessionDate.isoformat() if self.sessionDate else None,
            'startTime': self.startTime.strftime('%H:%M') if self.startTime else None,
            'endTime': self.endTime.strftime('%H:%M') if self.endTime else None,
            'durationMinutes': self.durationMinutes,
            'status': self.status,
            'notes': self.notes
        }


class LibraryResource(db.Model):
    __tablename__ = 'library_resources'

    id = db.Column(db.String(128), primary_key=True)
    uploaderId = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=False, index=True)
    skillTag = db.Column(db.String(100), nullable=True, index=True)
    resourceType = db.Column(db.String(50), nullable=False)
    fileUrl = db.Column(db.String(500), nullable=True)
    fileName = db.Column(db.String(255), nullable=True)
    fileSizeBytes = db.Column(db.BigInteger, default=0)
    isPublic = db.Column(db.Boolean, default=True)
    downloadsCount = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'uploaderId': self.uploaderId,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'skillTag': self.skillTag,
            'resourceType': self.resourceType,
            'fileUrl': self.fileUrl,
            'fileName': self.fileName,
            'fileSizeBytes': self.fileSizeBytes,
            'isPublic': self.isPublic,
            'downloadsCount': self.downloadsCount,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
