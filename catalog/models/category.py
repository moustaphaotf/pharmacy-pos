"""
Modèles pour les catégories et formes galéniques.
"""

from django.db import models

from pharmacy_pos.common.models import TimeStampedModel


class Category(TimeStampedModel):
    name = models.CharField('Nom', max_length=150, unique=True)
    code = models.CharField('Code', max_length=50, unique=True)
    description = models.TextField('Description', blank=True)

    class Meta:
        verbose_name = 'Catégorie'
        verbose_name_plural = 'Catégories'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class DosageForm(TimeStampedModel):
    name = models.CharField('Nom', max_length=150, unique=True)

    class Meta:
        verbose_name = 'Forme galénique'
        verbose_name_plural = 'Formes galéniques'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name

