from django.contrib.messages import get_messages

from .models import Message


def django_messages(request):
    return {'django_messages': get_messages(request)}


def unread_message_summary(request):
    if not request.user.is_authenticated:
        return {'unread_messages_count': 0}
    return {
        'unread_messages_count': Message.objects.filter(
            recipient=request.user,
            is_read=False,
        ).count()
    }
