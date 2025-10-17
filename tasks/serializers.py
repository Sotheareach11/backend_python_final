from datetime import date
from rest_framework import serializers
from .models import Task

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['id', 'title', 'team']
        read_only_fields = ['id']

    def validate(self, data):
        user = self.context['request'].user
        today = date.today()
        team = data.get('team')

        # 1️⃣ Admins and subscription users have no limit
        if user.is_superuser or getattr(user, 'user_type', None) in ['admin', 'subscription']:
            return data

        # 2️⃣ Limit per user (basic users: 5 tasks per day)
        today_user_count = Task.objects.filter(
            user=user, created_at__date=today
        ).count()
        if getattr(user, 'user_type', None) == 'basic' and today_user_count >= 5:
            raise serializers.ValidationError("Basic users can only create 5 tasks per day.")

        # 3️⃣ Limit per team (optional: e.g. 20 tasks per team per day)
        if team:
            today_team_count = Task.objects.filter(
                team=team, created_at__date=today
            ).count()
            if today_team_count >= 6:
                raise serializers.ValidationError(
                    f"Team '{team.name}' already reached the daily task limit (6)."
                )

        return data
