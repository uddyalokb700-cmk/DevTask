from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    """Extended user profile information for DevTask users."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=150, blank=True, help_text="Custom display name")
    bio = models.TextField(blank=True, help_text="Short bio or role description")
    avatar_color = models.CharField(max_length=7, default="#3b82f6", help_text="Hex color code for avatar")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.username} Profile"

    def get_display_name(self):
        return self.display_name.strip() or self.user.get_full_name().strip() or self.user.username
