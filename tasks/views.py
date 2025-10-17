from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied
from .models import Task
from .serializers import TaskSerializer

class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Limit tasks to the current user unless admin."""
        user = self.request.user
        if user.is_staff or user.is_superuser:
            # Admin can see all tasks
            return Task.objects.all()
        # Regular users can see only their own tasks
        return Task.objects.filter(user=user)

    def perform_create(self, serializer):
        """Assign the task to the logged-in user when creating."""
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        """Restrict normal users from deleting others’ tasks."""
        user = self.request.user
        if instance.user != user and not user.is_staff:
            raise PermissionDenied("You can only delete your own tasks.")
        instance.delete()
