from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = 'admin', 'Administrateur'
        CASHIER = 'cashier', 'Caissier'
        PHARMACIST = 'pharmacist', 'Pharmacien'

    role = models.CharField(
        verbose_name='Rôle',
        max_length=20,
        choices=Roles.choices,
        default=Roles.CASHIER,
    )

    def __str__(self) -> str:
        full_name = self.get_full_name()
        display_name = full_name or self.username
        return f'{display_name} ({self.get_role_display()})'

    class Meta(AbstractUser.Meta):
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
